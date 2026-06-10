"""
Evaluate the Claude drug-ADE extraction model against test_dataset.jsonl.

Reproduces the exact metrics from model.txt:
  test/json_validity        – fraction of responses that parse as valid JSON
  test/schema_validity      – fraction with the required {drug, adverse_effect, sentence} keys
  test/drug_exact_match     – fraction where pred_drug == true_drug (case-insensitive)
  test/ade_exact_match      – fraction where pred_ade == true_ade (case-insensitive)
  test/overall_exact_match  – both drug AND ade match
  test/hallucination_rate   – fraction where a predicted entity is absent from the source sentence

Usage:
  python AiHarness/evals/run_model_eval.py [--dataset path/to/test_dataset.jsonl]
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / ".env")

import anthropic

REQUIRED_KEYS = {"drug", "adverse_effect", "sentence"}

SYSTEM_PROMPT = """You are a clinical pharmacovigilance extraction system.

Given a medical sentence, extract the drug name and its associated adverse effect.

Return ONLY valid JSON with keys: "drug", "adverse_effect", "sentence".
Do not explain anything."""

client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])


def predict(sentence: str) -> str:
    """Run the model on a single sentence; return raw response text (JSON only)."""
    import re
    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=256,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": sentence}],
    )
    raw = response.content[0].text.strip()
    # Strip markdown code fences that some models wrap around JSON
    raw = re.sub(r"^```(?:json)?\s*", "", raw)
    raw = re.sub(r"\s*```$", "", raw)
    return raw.strip()


def evaluate(dataset_path: Path) -> dict:
    with dataset_path.open() as f:
        rows = [json.loads(line) for line in f if line.strip()]

    if not rows:
        print("Dataset is empty. Run build_test_dataset.py first.")
        sys.exit(1)

    print(f"Evaluating {len(rows)} examples from {dataset_path.name}...\n")

    results = []

    for i, row in enumerate(rows, 1):
        sentence = row["sentence"]
        true_drug = row["drug"].lower().strip()
        true_ade = row["adverse_effect"].lower().strip()

        pred_text = predict(sentence)

        valid_json = False
        schema_valid = False
        pred_drug = ""
        pred_ade = ""
        hallucinated = False

        try:
            parsed = json.loads(pred_text)
            valid_json = True
            # Unwrap a single-element list if the model returned [{...}]
            if isinstance(parsed, list) and len(parsed) == 1:
                parsed = parsed[0]
            if isinstance(parsed, dict) and REQUIRED_KEYS.issubset(parsed.keys()):
                schema_valid = True
                pred_drug = str(parsed.get("drug", "")).lower().strip()
                pred_ade = str(parsed.get("adverse_effect", "")).lower().strip()
                hallucinated = (
                    (pred_drug and pred_drug not in sentence.lower())
                    or (pred_ade and pred_ade not in sentence.lower())
                )
        except (json.JSONDecodeError, ValueError):
            pass

        result = {
            "sentence": sentence,
            "source_file": row.get("source_file", ""),
            "true_drug": true_drug,
            "true_ade": true_ade,
            "pred_json": pred_text,
            "valid_json": valid_json,
            "schema_valid": schema_valid,
            "pred_drug": pred_drug,
            "pred_ade": pred_ade,
            "drug_exact_match": pred_drug == true_drug,
            "ade_exact_match": pred_ade == true_ade,
            "hallucinated": hallucinated,
        }
        results.append(result)

        status = (
            "✓" if (result["drug_exact_match"] and result["ade_exact_match"]) else "✗"
        )
        print(
            f"[{i:>3}/{len(rows)}] {status} "
            f"drug: {true_drug!r:20s} → {pred_drug!r:20s}  "
            f"ade: {true_ade!r:30s} → {pred_ade!r:30s}"
        )

    n = len(results)
    metrics = {
        "test/json_validity": sum(r["valid_json"] for r in results) / n,
        "test/schema_validity": sum(r["schema_valid"] for r in results) / n,
        "test/drug_exact_match": sum(r["drug_exact_match"] for r in results) / n,
        "test/ade_exact_match": sum(r["ade_exact_match"] for r in results) / n,
        "test/overall_exact_match": sum(
            (r["drug_exact_match"] and r["ade_exact_match"]) for r in results
        )
        / n,
        "test/hallucination_rate": sum(r["hallucinated"] for r in results) / n,
    }

    # ── Print report ──────────────────────────────────────────────────────────
    print("\n" + "=" * 60)
    print("EVAL RESULTS")
    print("=" * 60)
    for k, v in metrics.items():
        bar = "█" * int(v * 20)
        print(f"  {k:<35s} {v:.4f}  {bar}")

    # ── Failures ──────────────────────────────────────────────────────────────
    failures = [
        r
        for r in results
        if not r["drug_exact_match"] or not r["ade_exact_match"]
    ]
    if failures:
        print(f"\n── Failures ({len(failures)}) ──")
        for r in failures[:10]:  # show first 10
            print(f"  Sentence   : {r['sentence'][:80]}")
            print(f"  True       : drug={r['true_drug']!r}  ade={r['true_ade']!r}")
            print(f"  Predicted  : drug={r['pred_drug']!r}  ade={r['pred_ade']!r}")
            if not r["valid_json"]:
                print(f"  Raw output : {r['pred_json'][:100]}")
            print()

    # ── Save detailed results ─────────────────────────────────────────────────
    results_path = dataset_path.parent / "eval_results.jsonl"
    with results_path.open("w") as f:
        for r in results:
            f.write(json.dumps(r) + "\n")
    print(f"Detailed results saved to {results_path}")

    return metrics


def main() -> None:
    parser = argparse.ArgumentParser(description="Run drug-ADE model eval")
    parser.add_argument(
        "--dataset",
        default=str(Path(__file__).parent / "test_dataset.jsonl"),
        help="Path to JSONL test dataset",
    )
    args = parser.parse_args()

    dataset_path = Path(args.dataset)
    if not dataset_path.exists():
        print(
            f"Dataset not found at {dataset_path}\n"
            "Run build_test_dataset.py first to generate it."
        )
        sys.exit(1)

    evaluate(dataset_path)


if __name__ == "__main__":
    main()
