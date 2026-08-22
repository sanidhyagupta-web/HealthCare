---
title: "Hybrid retrieval endpoint: correct scope to reflect existing implementation and post-retrieval access control"
date: 2026-08-22
id: DEC-0006
feature: hybrid-search
source_meeting: "Linear ticket ABC-6"
recording_id: ABC-6
transcript_id: https://linear.app/flightdecktest-2/issue/ABC-6/dec-0002-hybrid-retrieval-search-endpoint-bm25-vector-rrf
type: superseded
evidence_quote: "This is currently wired into the Streamlit UI's search flow (`ui/search_page.py`), not exposed as a standalone endpoint — but the retrieval logic itself is not new work."
reconciliation:
  existed_before: true
  previously_rejected: false
  contradicts: [DEC-0002]
  on_roadmap: true
  dependencies: [DEC-0002]
  changes_plan: true
supersedes: [DEC-0002]
linear_issue: https://linear.app/flightdecktest-2/issue/ABC-6/dec-0002-hybrid-retrieval-search-endpoint-bm25-vector-rrf
---

## Statement
The hybrid retrieval search endpoint work is corrected in scope: hybrid retrieval (BM25 + vector search + RRF + cross-encoder rerank) already exists end-to-end in `ui/search_page.py`/`indexing/*` and is not new work, and the caller's access scope must continue to be enforced through the existing, documented, non-negotiable post-retrieval RBAC pipeline (`filter_results_by_role` → `apply_role_mask` in `security/access_control.py`/`search/pipeline.py`) rather than filtered inside the query itself, superseding DEC-0002's contrary claims.

## Reconciliation Notes
Codebase-reality check (product-align-loop, Linear ticket ABC-6) found that hybrid retrieval already exists end-to-end in this codebase, contradicting DEC-0002's premise that no prior retrieval implementation exists; and DEC-0002's in-query access-filtering requirement contradicts the codebase's documented, non-negotiable post-retrieval RBAC pattern (`AiHarness/skills/access-control.md`, `security/access_control.py`, `search/pipeline.py`). This supersedes DEC-0002 rather than a plain rejection, since the underlying need for a standalone hybrid-search endpoint still stands — only the "net-new work" framing and the in-query-filtering requirement are corrected.
