"""
Search page — full query pipeline:

  Rate limit
    → Input guardrail
      → PII detection on query (Presidio / regex)
        → Hash lookup → Top-D chunk filter
          → Vector (Chroma) + BM25 → RRF merge
            → Cross-encoder re-rank (Top-K)
              → Claude LLM (with citations)
                → Output guardrail (PII sanitisation)
                  → Display answer + source citations
"""
from __future__ import annotations
import streamlit as st

from security.access_control import filter_results_by_role
from security.audit_logger import log_event
from security.auth import current_user
from security.guardrails import check_input, sanitise_output
from app.dependencies import rate_limiter
from indexing.reranker import rerank
from indexing.pii_entity_index import get_chunk_ids_for_entities
from ingestion.pii.pii_detector import detect_pii
from llm.claude_client import generate_answer


# ── Internal search helpers ───────────────────────────────────────────────────

def _vector_search(
    query: str,
    n: int,
    role: str,
    chunk_id_filter: set[str] | None = None,
) -> list[dict]:
    try:
        from indexing.embeddings import embed_query
        from indexing.chroma_store import query as chroma_query

        where = None
        if chunk_id_filter:
            where = {"chunk_id": {"$in": list(chunk_id_filter)}}

        raw = chroma_query(query_embedding=embed_query(query), n_results=n, where=where)
        return filter_results_by_role(raw, role)
    except Exception as e:
        st.warning(f"Vector search unavailable: {e}")
        return []


def _keyword_search(
    query: str,
    n: int,
    role: str,
    chunk_id_filter: set[str] | None = None,
) -> list[dict]:
    try:
        from indexing.opensearch_index import keyword_search, keyword_search_filtered
        if chunk_id_filter:
            raw = keyword_search_filtered(query, n_results=n, chunk_id_filter=chunk_id_filter)
        else:
            raw = keyword_search(query, n_results=n)
        return filter_results_by_role(raw, role)
    except Exception as e:
        st.warning(f"Keyword search unavailable: {e}")
        return []


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


def _highlight(text: str, query: str) -> str:
    import re
    for word in query.split():
        if len(word) > 2:
            text = re.sub(rf"(?i)({re.escape(word)})", r"**\1**", text)
    return text


# ── Page render ───────────────────────────────────────────────────────────────

def render() -> None:
    user = current_user()
    role = user["role"]
    username = user["username"]

    st.header("Search Medical Records")

    col1, col2 = st.columns([3, 1])
    with col1:
        query = st.text_input(
            "Natural language query",
            placeholder="What medications is the patient with MRN57574 taking?",
        )
    with col2:
        st.text_input("Signed in as", value=f"{user['display_name']} ({role})", disabled=True)

    with st.expander("Search options", expanded=False):
        c1, c2, c3 = st.columns(3)
        with c1:
            n_results = st.slider("Final results (top-K)", 3, 20, 5)
        with c2:
            alpha = st.slider(
                "Vector vs keyword balance", 0.0, 1.0, 0.6,
                help="1.0 = pure vector  |  0.0 = pure keyword",
            )
        with c3:
            search_mode = st.radio("Mode", ["Hybrid", "Vector only", "Keyword only"])

    if not query:
        st.info("Enter a query to search across ingested medical records.")
        return

    if st.button("Search", type="primary"):

        # ── 1. Rate limit ─────────────────────────────────────────────────────
        if not rate_limiter.is_allowed(username):
            st.error("Rate limit exceeded — max 10 queries/minute. Please wait.")
            log_event("RATE_LIMITED", user_id=username, query=query)
            return

        # ── 2. Input guardrail ────────────────────────────────────────────────
        is_safe, reason = check_input(query)
        if not is_safe:
            st.error(f"Query blocked: {reason}")
            log_event("GUARDRAIL_BLOCKED", user_id=username, query=query,
                      details={"reason": reason})
            return

        # ── 3. PII detection on query → hash lookup → Top-D filter ────────────
        query_entities = detect_pii(query)
        chunk_id_filter: set[str] | None = None

        if query_entities:
            matched_ids = get_chunk_ids_for_entities(query_entities)
            if matched_ids:
                chunk_id_filter = matched_ids
                entity_labels = ", ".join(
                    f"`{e.entity_type}:{e.text}`" for e in query_entities
                )
                st.caption(
                    f"PII detected in query: {entity_labels} "
                    f"— pre-filtering to **{len(matched_ids)}** matching chunks (Top-D)"
                )

        # ── 4. Retrieval (Vector + BM25) ──────────────────────────────────────
        with st.spinner("Searching…"):
            candidate_pool = max(n_results * 4, 20)

            if search_mode == "Hybrid":
                vec_res = _vector_search(query, candidate_pool, role, chunk_id_filter)
                kw_res = _keyword_search(query, candidate_pool, role, chunk_id_filter)
                candidates = _rrf_merge(vec_res, kw_res, alpha)
            elif search_mode == "Vector only":
                candidates = _vector_search(query, candidate_pool, role, chunk_id_filter)
            else:
                candidates = _keyword_search(query, candidate_pool, role, chunk_id_filter)

        # ── 5. Cross-encoder re-ranking ───────────────────────────────────────
        with st.spinner("Re-ranking with cross-encoder…"):
            top_chunks = rerank(query, candidates, top_k=n_results)

        # ── 6. LLM answer generation ──────────────────────────────────────────
        with st.spinner("Generating answer with Claude…"):
            raw_answer, cited_indices = generate_answer(query, top_chunks, role)

        # ── 7. Output guardrail (PII sanitisation) ────────────────────────────
        answer = sanitise_output(raw_answer)

        # ── 8. Audit log ──────────────────────────────────────────────────────
        log_event("SEARCH", user_id=username, query=query,
                  details={
                      "mode": search_mode,
                      "n_results": len(top_chunks),
                      "role": role,
                      "pii_filter_applied": chunk_id_filter is not None,
                      "cited_excerpts": cited_indices,
                  })

        if not top_chunks:
            st.warning("No results found. Try a broader query or ingest more documents.")
            return

        # ── 9. Display answer ─────────────────────────────────────────────────
        st.markdown("### Answer")
        st.info(answer)

        # ── 10. Citations ─────────────────────────────────────────────────────
        if cited_indices:
            st.markdown("### Citations")
            for idx in cited_indices:
                chunk = top_chunks[idx - 1]   # 1-based → 0-based
                meta = chunk.get("metadata", {})
                with st.expander(
                    f"[{idx}]  {meta.get('source_section', 'Unknown')}  ·  "
                    f"{meta.get('source_file', '—')}  ·  "
                    f"Page {meta.get('source_page', '—')}  ·  "
                    f"Dept: {meta.get('department', '—')}",
                    expanded=False,
                ):
                    st.markdown(_highlight(chunk.get("text", ""), query))
                    c1, c2, c3 = st.columns(3)
                    c1.metric("Patient ID", meta.get("patient_id", "—"))
                    c2.metric("Doc ID", str(meta.get("doc_id", "—"))[:10] + "…")
                    c3.metric("Rerank score", f"{chunk.get('rerank_score', 0):.3f}")

        # ── 11. All supporting excerpts ───────────────────────────────────────
        with st.expander(f"All {len(top_chunks)} retrieved excerpts", expanded=False):
            for i, r in enumerate(top_chunks, 1):
                meta = r.get("metadata", {})
                cited_marker = " ✦" if i in cited_indices else ""
                st.markdown(
                    f"**[{i}]{cited_marker}  {meta.get('source_section', '—')}**  "
                    f"·  `{meta.get('source_file', '—')}`  "
                    f"·  rerank `{r.get('rerank_score', 0):.3f}`"
                )
                st.markdown(_highlight(r.get("text", ""), query))
                st.markdown("---")
