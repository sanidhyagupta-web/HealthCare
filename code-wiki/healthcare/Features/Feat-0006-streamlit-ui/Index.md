---
feat_id: Feat-0006
feature: streamlit-ui
type: frontend-feature
domain: user-interface
criticality: high
touched_paths:
  - ui/
depends_on: [Feat-0007-security-access-control, Feat-0005-semantic-search-qa, Feat-0002-document-indexing, Feat-0003-document-ingestion, Feat-0004-pipeline-workers, Feat-0008-storage-persistence]
consumed_by: []
implements: []
tags: [streamlit, frontend, ui]
---

## Overview

| | |
|---|---|
| Type | frontend-feature (Streamlit — Python-rendered, no React/TS/separate JS build) |
| Package | `ui/` |
| Path | `ui/streamlit_app.py`, `ui/login_page.py`, `ui/search_page.py`, `ui/upload_page.py`, `ui/bulk_upload_page.py`, `ui/audit_page.py` |
| Domain | The entire user-facing surface of the product |
| Last updated | initial scan |

## Domain Purpose

The only human-facing entry point to the system. Gates access behind login, then routes to four
pages: semantic search & Q&A, single-document upload, bulk upload, and an audit/DLQ viewer.

## What This Does for the User

A clinician/staff member logs in, sees a role- and department-labeled sidebar, and can search
medical records in natural language (with citations), upload new documents (singly or in bulk,
role-gated), and — for anyone with access to the page — review the audit trail and dead-letter
queue of failed ingestions.

## Key User Flows

| Flow | What Happens |
|---|---|
| Login | username/password → `security.auth.login()` → on success `st.rerun()` reveals the authenticated shell; on failure or empty fields, an inline error, no lockout |
| Search | query → rate limit check → input guardrail → PII detection (pre-filters candidate chunks) → hybrid vector+keyword retrieval, RBAC-filtered → rerank → `generate_answer()` ([[Feat-0005-semantic-search-qa]]) → output sanitized → cited answer + expandable source excerpts |
| Single upload | file + patient/department metadata → `ingest_document()` ([[Feat-0003-document-ingestion]]) → status table of recent documents, polled by manual refresh only |
| Bulk upload | role check (doctor/nurse/admin only) → up to 50 files → per-file queued/rejected result table |
| Audit review | filter by doc ID / row limit → event table; separate tab lists DLQ messages with full JSON payload |
| Logout | `security.auth.logout()` clears session state → `st.rerun()` returns to login |

## UI States

| Condition | What Renders |
|---|---|
| Not authenticated | login form only, no sidebar |
| Login submitted with missing fields | inline error, no page transition |
| Rate limit exceeded (search or upload) | inline error, operation aborted, logged as `RATE_LIMITED` |
| Guardrail-blocked query | inline error, search aborted, logged as `GUARDRAIL_BLOCKED` |
| PII detected in the query itself | caption showing matched entities; results pre-filtered to matching chunks |
| No search results after RBAC filtering | warning, no crash |
| Bulk upload, role not allowed | error message, page stops rendering (no partial form) |
| Bulk upload, >50 files selected | inline error, upload blocked |
| DLQ empty vs. populated | success banner vs. expandable per-message rows |

## APIs Consumed

| Method | Path / Call | Owning Feature |
|---|---|---|
| in-process call | `ingest_document()`, `_process_single_upload_bytes()` | [[Feat-0003-document-ingestion]] |
| in-process call | `embed_query()`, `chroma_query()`, `keyword_search()`, `keyword_search_filtered()`, `rerank()`, `get_chunk_ids_for_entities()` | [[Feat-0002-document-indexing]] |
| in-process call | `generate_answer()` | [[Feat-0005-semantic-search-qa]] |
| in-process call | `filter_results_by_role()`, `check_input()`, `sanitise_output()`, `login()`, `is_authenticated()`, `current_user()`, `logout()`, `log_event()`, `get_audit_trail()` | [[Feat-0007-security-access-control]] |
| in-process call | `init_db()`, `get_db()`, `DocumentRegistry` queries | [[Feat-0008-storage-persistence]] |
| in-process call | `dlq.list_messages()` | [[Feat-0004-pipeline-workers]] |

**Note**: every one of these is an in-process Python function call, not an HTTP request — there is
no API-client layer or state-management store in this app. `st.session_state` *is* the state layer.

## State

No Redux/Zustand/TanStack-style store. State lives entirely in Streamlit's own
`st.session_state`, written by `security/auth.py::login()`/`logout()`:
`authenticated: bool`, `username`, `role`, `department`, `display_name`.

## Access Control

**Model**: session-based, and the *only* place in the whole repo where login/role gating exists.

| Action | Access Condition | Enforced In |
|---|---|---|
| Any page render | `is_authenticated()` | `ui/streamlit_app.py` |
| Bulk upload page | `role ∈ get_ingest_allowed_roles()` | `ui/bulk_upload_page.py` |
| Search result visibility | `filter_results_by_role()` | delegated to [[Feat-0007-security-access-control]] via [[Feat-0005-semantic-search-qa]] |

## Safe vs Dangerous Changes

### Safe
- Adding a new page to the sidebar `PAGES` dict, as long as it re-checks `is_authenticated()` at render (Streamlit re-runs the whole script on every interaction, so this isn't automatic — each page function does its own check)

### Dangerous — Requires Review
| Change | Risk | Why |
|---|---|---|
| Removing or weakening the `is_authenticated()` gate in `streamlit_app.py` | This is the sole login enforcement point for the entire product | 
| Changing what `bulk_upload_page.py` calls (`ingest_document()` vs. hitting the `/ingest/bulk` HTTP route) | Currently calls the Python function in-process — switching to HTTP changes error handling, auth (self-asserted header vs. none), and latency characteristics |

### Human Escalation Required
- Any move toward a real auth mechanism (tokens/cookies/SSO) — today session state is purely server-process-local with no persistence across restarts, which may or may not be acceptable for the intended deployment.

## Known Error Scenarios

| Scenario | Error Returned | Root Cause |
|---|---|---|
| Invalid credentials | "Invalid username or password." | `login()` returns `False` |
| Empty username/password | "Please enter both username and password." | client-side check before calling `login()` |
| Vector/keyword search backend unavailable | inline warning, degraded (partial) results | caught around each retrieval call |
| No documents ingested yet | info message, not an error | empty state |

## Testing Expectations

*Open question: no tests exist under `ui/` today.* See the `frontend-test` skill
(`.claude/skills/frontend-test/SKILL.md`) for the recommended approach using Streamlit's
`AppTest` harness (`streamlit.testing.v1`) — pytest-based, no separate JS test runner needed.

## Key Files

- `ui/streamlit_app.py` — entry point, auth gate, sidebar navigation
- `ui/login_page.py` — login form (demo credentials shown inline: `admin`/`dr_smith`/`nurse_jones`/`radiologist_lee`/`billing_dept`)
- `ui/search_page.py` — the full query pipeline UI (heaviest page — rate limit, guardrails, PII pre-filter, retrieval, rerank, LLM, output sanitization, citations)
- `ui/upload_page.py`, `ui/bulk_upload_page.py` — single and batch ingest UIs
- `ui/audit_page.py` — audit trail + DLQ viewer (two tabs)

## Context Routing

| Feature | Load when |
|---|---|
| Feat-0006-streamlit-ui | touching any page's rendering, the login gate, or the sidebar navigation |

## Forbidden Patterns

- Never render page content before checking `is_authenticated()` — Streamlit has no framework-level route guard; each page is responsible for its own check.
- Never display raw LLM output without routing it through `sanitise_output()` first (see `search_page.py`'s existing pattern).

## Known Gaps

- No auto-refresh/polling for document status or audit events — the user must manually refresh to see pipeline progress.
- Filesize limits are inconsistently surfaced: mentioned in bulk upload's help text but not in the single-upload page's UI copy.
- Workers are started lazily (`_ensure_workers()`) from `upload_page.py`/`bulk_upload_page.py` — if a user never visits either page, the pipeline never starts consuming its queues.
