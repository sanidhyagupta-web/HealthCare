# Eval Case 02 — Expected Output

## Templates
- [ ] `features/active/search-endpoint/01-product-spec.md` — user is "doctor/nurse/admin", success criteria include role validation, audit log presence, and citation format
- [ ] `features/active/search-endpoint/02-technical-spec.md` — architecture: "Search / retrieval", touches `app/main.py`, `indexing/`, `security/`, `llm/`; skills listed: `hybrid-search.md`, `audit-logging.md`, `access-control.md`, `llm-response-validation.md`
- [ ] `features/active/search-endpoint/03-implementation-plan.md` — steps in order: role validation → retrieval → RRF → rerank → RBAC filter → role mask → audit → LLM → response

## Code: app/main.py additions
- `POST /search` route added
- Pydantic request model: `SearchRequest(query: str, role: str)`
- Role validated against the known role set from `rbac_policy.py` — 422 if unknown role
- `embed_texts([query])` called to get query embedding
- Both `query_chunks(embedding, n_results=20)` and BM25 retrieval called
- `rrf_merge(vector_results, keyword_results, alpha=0.6)` called — correct alpha
- `rerank(query, rrf_top20, top_k=5)` called
- `filter_results_by_role(top5, role)` called **before** `generate_answer`
- `apply_role_mask(chunks, role)` called on filtered results
- `log_event("QUERY_SUBMITTED", ...)` called with hashed query, role, result chunk IDs — no raw query text in log
- `generate_answer(query, masked_chunks, role)` called
- Response shape: `{"answer": str, "sources": [{"chunk_id", "source_file", "source_section", "page"}]}`
- No-answer case handled: if `generate_answer` returns the "not enough information" string, `sources` is `[]`

## Conventions respected
- `filter_results_by_role` called before LLM, not after
- Audit log uses `log_event()` from `security/audit_logger.py`, not a new logger
- `query_hash` in audit log, not raw query string
- `llm/claude_client.py` is the only place Claude is called — no `anthropic.Anthropic()` inline

## Non-negotiables respected
- No hardcoded role strings inline — validated against `rbac_policy.py`
- No unfiltered chunks passed to LLM
- Audit log entry present for every request including failed ones (400/422)

## Tests expected
- Unit test: `POST /search` with `role="admin"` returns `sources` with `[REDACTED]` clinical content
- Unit test: `POST /search` with unknown `role="hacker"` returns 422
- Integration test: query that matches a seeded document returns `answer` containing `[1]` citation

## What failing looks like
- Agent filters results after `generate_answer` — LLM sees forbidden chunks
- Agent logs raw query text in audit event
- Agent calls `anthropic.Anthropic()` directly in `main.py` instead of `llm/claude_client.py`
- Agent skips BM25 and does vector-only retrieval
- Agent creates a new audit module instead of using `security/audit_logger.py`
