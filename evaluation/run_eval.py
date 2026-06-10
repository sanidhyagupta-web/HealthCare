#!/usr/bin/env python3
"""
Healthcare retrieval evaluation with LangSmith.

Measures Hit@1, Hit@3, Hit@5, MRR@5, and Precision@3/5 for the hybrid
retrieval pipeline (vector + BM25 → RRF → cross-encoder rerank).

Usage:
    cd /path/to/Healthcare
    python evaluation/run_eval.py
"""
from __future__ import annotations
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.config import settings  # loads .env

from indexing.embeddings import embed_query
from indexing.chroma_store import query as chroma_query
from indexing.opensearch_index import keyword_search
from indexing.reranker import rerank
from security.access_control import filter_results_by_role

DATASET_NAME = "healthcare-retrieval-eval-v1"
EVAL_ROLE = "admin"   # admin bypasses RBAC so we test retrieval quality, not access policy
TOP_K = 5
ALPHA = 0.6           # 60% vector / 40% keyword — same as UI default


# ── Retrieval helpers (copied from search_page, no Streamlit dependency) ─────

def _rrf_merge(vector: list[dict], keyword: list[dict], alpha: float) -> list[dict]:
    scores: dict[str, float] = {}
    merged: dict[str, dict] = {}
    for rank, r in enumerate(vector):
        cid = r["chunk_id"]
        scores[cid] = scores.get(cid, 0) + alpha * (1 / (rank + 1))
        merged[cid] = r
    for rank, r in enumerate(keyword):
        cid = r["chunk_id"]
        scores[cid] = scores.get(cid, 0) + (1 - alpha) * (1 / (rank + 1))
        if cid not in merged:
            merged[cid] = r
    ranked = sorted(merged.values(), key=lambda r: scores[r["chunk_id"]], reverse=True)
    for r in ranked:
        r["hybrid_score"] = round(scores[r["chunk_id"]], 4)
    return ranked


def _retrieve(query: str, top_k: int = TOP_K, alpha: float = ALPHA) -> list[str]:
    """Run the full hybrid pipeline and return ordered chunk IDs."""
    candidate_pool = max(top_k * 4, 20)
    vec_res = filter_results_by_role(
        chroma_query(embed_query(query), n_results=candidate_pool), EVAL_ROLE
    )
    kw_res = filter_results_by_role(
        keyword_search(query, n_results=candidate_pool), EVAL_ROLE
    )
    candidates = _rrf_merge(vec_res, kw_res, alpha)
    top_chunks = rerank(query, candidates, top_k=top_k)
    return [c["chunk_id"] for c in top_chunks]


# ── LangSmith target function ─────────────────────────────────────────────────

def retrieve_target(inputs: dict) -> dict:
    chunk_ids = _retrieve(inputs["query"])
    return {"retrieved_chunk_ids": chunk_ids}


# ── Evaluators ────────────────────────────────────────────────────────────────

def _make_hit_at_k(k: int):
    def evaluator(outputs: dict, reference_outputs: dict) -> dict:
        retrieved = outputs.get("retrieved_chunk_ids", [])[:k]
        relevant = set(reference_outputs.get("relevant_chunk_ids", []))
        return {"key": f"hit_at_{k}", "score": float(any(c in relevant for c in retrieved))}
    evaluator.__name__ = f"hit_at_{k}"
    return evaluator


def _make_mrr_at_k(k: int):
    def evaluator(outputs: dict, reference_outputs: dict) -> dict:
        retrieved = outputs.get("retrieved_chunk_ids", [])[:k]
        relevant = set(reference_outputs.get("relevant_chunk_ids", []))
        rr = next((1.0 / (rank + 1) for rank, cid in enumerate(retrieved) if cid in relevant), 0.0)
        return {"key": f"mrr_at_{k}", "score": rr}
    evaluator.__name__ = f"mrr_at_{k}"
    return evaluator


def _make_precision_at_k(k: int):
    def evaluator(outputs: dict, reference_outputs: dict) -> dict:
        retrieved = outputs.get("retrieved_chunk_ids", [])[:k]
        relevant = set(reference_outputs.get("relevant_chunk_ids", []))
        score = sum(1 for c in retrieved if c in relevant) / k if retrieved else 0.0
        return {"key": f"precision_at_{k}", "score": score}
    evaluator.__name__ = f"precision_at_{k}"
    return evaluator


# ── Dataset management ────────────────────────────────────────────────────────

def _ensure_dataset(client, test_cases: list[dict]):
    existing = [d for d in client.list_datasets() if d.name == DATASET_NAME]
    if existing:
        dataset = existing[0]
        count = sum(1 for _ in client.list_examples(dataset_id=dataset.id))
        print(f"Using existing LangSmith dataset '{DATASET_NAME}' ({count} examples)")
        return dataset

    dataset = client.create_dataset(
        DATASET_NAME,
        description="Ground-truth retrieval QA pairs for Healthcare Semantic Search pipeline.",
    )
    for tc in test_cases:
        client.create_example(
            inputs={"query": tc["query"]},
            outputs={"relevant_chunk_ids": tc["relevant_chunk_ids"]},
            metadata={"notes": tc.get("notes", ""), "target_section": tc.get("target_section", "")},
            dataset_id=dataset.id,
        )
    print(f"Created LangSmith dataset '{DATASET_NAME}' with {len(test_cases)} examples.")
    return dataset


# ── Local fallback (no LangSmith) ────────────────────────────────────────────

def _run_local(test_cases: list[dict]) -> None:
    print("\nRunning local evaluation (no LangSmith)…\n")
    metrics: dict[str, list[float]] = {
        "hit@1": [], "hit@3": [], "hit@5": [], "mrr@5": [], "p@3": [], "p@5": [],
    }

    for i, tc in enumerate(test_cases, 1):
        q = tc["query"]
        relevant = set(tc["relevant_chunk_ids"])
        retrieved = _retrieve(q)
        print(f"[{i:02d}] {q[:70]}")
        print(f"      relevant={[r[:8] for r in relevant]}  retrieved={[r[:8] for r in retrieved]}")

        metrics["hit@1"].append(float(any(c in relevant for c in retrieved[:1])))
        metrics["hit@3"].append(float(any(c in relevant for c in retrieved[:3])))
        metrics["hit@5"].append(float(any(c in relevant for c in retrieved[:5])))
        mrr = next((1.0 / (r + 1) for r, c in enumerate(retrieved[:5]) if c in relevant), 0.0)
        metrics["mrr@5"].append(mrr)
        metrics["p@3"].append(sum(1 for c in retrieved[:3] if c in relevant) / 3)
        metrics["p@5"].append(sum(1 for c in retrieved[:5] if c in relevant) / 5)

    print("\n── Retrieval Accuracy ────────────────────────────────────")
    for name, vals in metrics.items():
        avg = sum(vals) / len(vals)
        bar = "█" * round(avg * 20)
        print(f"  {name.upper():<12} {avg:.3f}  {bar}")


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    test_cases_path = Path(__file__).parent / "test_dataset.json"
    test_cases = json.loads(test_cases_path.read_text())
    print(f"Loaded {len(test_cases)} test cases from {test_cases_path.name}")

    langsmith_key = settings.langsmith_api_key
    if not langsmith_key:
        print("LANGSMITH_API_KEY not set — running local evaluation.\n")
        _run_local(test_cases)
        return

    from langsmith import Client
    from langsmith.evaluation import evaluate

    client = Client(api_key=langsmith_key)
    _ensure_dataset(client, test_cases)

    print(f"\nRunning LangSmith evaluation (top_k={TOP_K}, alpha={ALPHA})…")
    results = evaluate(
        retrieve_target,
        data=DATASET_NAME,
        evaluators=[
            _make_hit_at_k(1),
            _make_hit_at_k(3),
            _make_hit_at_k(5),
            _make_mrr_at_k(5),
            _make_precision_at_k(3),
            _make_precision_at_k(5),
        ],
        experiment_prefix="hybrid-retrieval",
        metadata={"top_k": TOP_K, "alpha": ALPHA, "role": EVAL_ROLE},
        max_concurrency=1,
    )

    print("\n── Retrieval Accuracy ────────────────────────────────────")
    try:
        df = results.to_pandas()
        feedback_cols = [c for c in df.columns if c.startswith("feedback.")]
        if feedback_cols:
            for col in feedback_cols:
                label = col.replace("feedback.", "").upper()
                avg = df[col].mean()
                bar = "█" * round(avg * 20)
                print(f"  {label:<15} {avg:.3f}  {bar}")
        else:
            print("  (Scores recorded in LangSmith — check the UI for details.)")
    except Exception:
        print("  (Could not aggregate scores locally — check LangSmith UI.)")

    project = settings.langsmith_project or "healthcare-semantic-search"
    print(f"\nFull traces → https://smith.langchain.com/projects/{project}")


if __name__ == "__main__":
    main()
