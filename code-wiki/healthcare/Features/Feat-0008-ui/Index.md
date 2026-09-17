---
feat_id: Feat-0008
feature: ui
type: frontend-feature
domain: streamlit-app
criticality: high
touched_paths:
  - ui/streamlit_app.py
  - ui/login_page.py
  - ui/upload_page.py
  - ui/bulk_upload_page.py
  - ui/search_page.py
  - ui/audit_page.py
depends_on: [app, platform, ingestion, indexing, security, llm, workers]
consumed_by: []
implements: []
tags: [streamlit, ui, rag-frontend]
---

## Overview

| Type | Package | Path | Domain | Last updated |
|---|---|---|---|---|
| frontend-feature | `ui` | `ui/` | The only frontend — a single-process Streamlit app | 2026-09-17 (initial scan) |

There is no separate frontend framework, HTTP API client layer, or build step in this repo — every
page imports backend Python modules directly and calls them in-process. "Frontend/backend" here
means "Streamlit page" vs. "everything else," not a network boundary.

## What This Does for the User

Lets clinical/admin/billing users log in, upload documents (single or bulk), run a RAG search over
ingested records, and (for any authenticated user, regardless of role — see [[security]] BR-04)
view the audit trail and dead-letter queue.

## Key User Flows

| Flow | User Action | What Happens |
|---|---|---|
| Login | enter username/password, submit | `security.auth.login()` checked; on success, `st.session_state` set and page reruns |
| Search | enter a query, click Search | rate-limit check → input guardrail → optional PII pre-filter → vector/keyword/hybrid retrieval → RBAC filter → rerank → LLM answer → output sanitization → display (see [[search]] for a gap in this chain) |
| Single upload | pick a file, fill uploader/patient/department, click Upload | `app.ingest_document()` called in-process; progress bar; recent-documents table refreshed |
| Bulk upload | pick up to 50 files, click Upload & Ingest Batch | role check (doctor/nurse/admin) → `app._process_single_upload_bytes()` per file → per-file results table |
| Audit review | optionally filter by doc ID, click Refresh | `security.audit_logger.get_audit_trail()` → table; separate tab shows the DLQ |

## UI States

| Condition | What Renders |
|---|---|
| not `is_authenticated()` | login page only |
| authenticated | sidebar with `{display_name, role, department}` + page navigation |
| search: empty query | `st.info("Enter a query…")` |
| search: no results | `st.warning("No results found…")` |
| search: PII detected in the query itself | `st.caption` showing matched entities, used to pre-filter |
| upload: file rejected | per-file `st.error` with the validator's reason |
| bulk upload: wrong role | `st.error("Access denied…")`, form not rendered |
| bulk upload: >50 files | `st.error`, upload blocked |
| audit: DLQ empty | `st.success("DLQ is empty…")` |
| audit: DLQ has messages | expander per message showing `dlq_reason`/`dlq_source`/`dlq_timestamp` |

## APIs Consumed

There is no HTTP API layer between `ui/` and the backend — every "call" below is an in-process Python import.

| Method | Path | Owning Feature |
|---|---|---|
| in-process | `security.auth.{login,is_authenticated,current_user,logout}` | Feat-0006-security |
| in-process | `security.access_control.filter_results_by_role` | Feat-0006-security |
| in-process | `security.guardrails.{check_input,sanitise_output}` | Feat-0006-security |
| in-process | `app.ingest_document`, `app._process_single_upload_bytes` | Feat-0001-app |
| in-process | `indexing.{chroma_store,opensearch_index,reranker,embeddings,pii_entity_index}` | Feat-0002-indexing |
| in-process | `llm.claude_client.generate_answer` | Feat-0004-llm |
| in-process (lazy) | `workers.{ParserWorker,...}` via `_ensure_workers()` | Feat-0007-workers |
| HTTP (only true network call in `ui/`) | none — search page never calls `llm/ade_api` directly; that's [[workers]]'s `ExtractionWorker` | — |

## State

No Redux/Zustand-style store — state is `st.session_state`, set once at login
(`security/auth.py:49-55`): `{authenticated, username, role, department, display_name}`. Per-page
transient state (search filters, upload progress) is local Streamlit widget state, not persisted
across reruns beyond what Streamlit itself keeps.

## Business Rules

| BR-NN | Rule | Enforced In | Severity |
|---|---|---|---|
| BR-01 | Rate limit (10/min, `app.dependencies.rate_limiter`) applied on search, single upload, and bulk upload | `search_page.py:135`, `upload_page.py:84`, `bulk_upload_page.py:106` | MEDIUM |
| BR-02 | Bulk upload capped at 50 files client-side too (mirrors the HTTP endpoint's cap) | `bulk_upload_page.py:99-101` | LOW |
| BR-03 | `search_page.py` calls `filter_results_by_role` but — per the [[search]] feature's escalation note — does **not** call `apply_role_mask` before `generate_answer()` | `search_page.py:45,63,169-183` | CRITICAL |
| BR-04 | Single-file `upload_page.py` has no ingest-role check, unlike `bulk_upload_page.py` | absence | HIGH |
| BR-05 | `audit_page.py` has no role gate — any authenticated user sees every user's audit events | absence | HIGH |

## Safe vs Dangerous Changes

### Safe
- Adjusting search UI controls (result count slider, hybrid-search alpha weight).
- Adding a new column to the recent-documents table.

### Dangerous — Requires Review
| Change | Risk | Why |
|---|---|---|
| Adding a new page that reads/writes chunks without going through `filter_results_by_role` | RBAC bypass | This is the only enforcement point for chunk-level access |
| Adding a new page that calls the LLM with retrieved chunks | Same PII-leak risk as the existing gap in `search_page.py` | See Feat-0005-search's escalation note before writing this pattern again |

### Human Escalation Required
- Restricting `audit_page.py` to admin-only.
- Adding the ingest-role check to `upload_page.py` (currently only `bulk_upload_page.py` has it).
- Fixing the missing `apply_role_mask()` call before `generate_answer()` in `search_page.py`.

## Known Error Scenarios

| Scenario | Error Returned | Root Cause |
|---|---|---|
| Bad credentials | `st.error("Invalid username or password.")` | `login_page.py:25` |
| Rate limit hit | `st.error` + `RATE_LIMITED` audit event | in-memory `RateLimiter`, process-scoped |
| Guardrail block | `st.error(f"Query blocked: {reason}")` + `GUARDRAIL_BLOCKED` audit event | `search_page.py:142-146` |
| Vector/keyword search backend unavailable | `st.warning`, that retrieval mode returns `[]`, other mode still tried | `search_page.py:46-48,64-66` |

## Testing Expectations

No test file exercises `ui/*.py` in `tests/unit/`. See `.claude/skills/frontend-test/SKILL.md` for
this repo's actual recommended approach (`streamlit.testing.v1.AppTest`, run under `pytest` — there
is no separate JS test runner since this is not a JS frontend).

## Forbidden Patterns

- Never add a new "search-like" flow that skips `filter_results_by_role` before showing chunk content.
- Never assume Streamlit's `st.session_state` is a secure session mechanism — see [[security]]'s auth gaps.

## Key Files

- `ui/streamlit_app.py` — entry point, auth gate, page routing
- `ui/login_page.py`, `upload_page.py`, `bulk_upload_page.py`, `search_page.py`, `audit_page.py` — one file per page

## Context Routing

| Feature | Load when |
|---|---|
| Feat-0008-ui | touching any Streamlit page, its state, or its role gating |

| Workflow | Sections to load |
|---|---|
| Adding a new page | Key User Flows, APIs Consumed, then the security note in Safe vs Dangerous Changes |
| Investigating a PII-in-answer report | Business Rules BR-03, then Feat-0005-search |
