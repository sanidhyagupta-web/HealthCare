---
feat_id: Feat-0004
feature: healthcare-semantic-search-ui
type: frontend-feature
domain: healthcare-document-search
criticality: high
touched_paths:
  - ui/
depends_on: [Feat-0001, Feat-0003, Feat-0005]
consumed_by: []
implements: []
tags: [streamlit, ui, rbac]
---

## Overview

| Type | Package | Path | Domain | Last updated |
|---|---|---|---|---|
| frontend-feature | (single package) | `ui/` | End-user access to ingestion, search, and audit | 2026-09-03 |

## Domain Purpose

The only user-facing surface of this system: a Streamlit app (no JS/React — this is a Python
"frontend") that lets a logged-in clinical/administrative user upload documents (single or bulk),
search across ingested records with an LLM-generated answer, and browse the audit trail / dead
letter queue.

## What This Does for the User

Log in, then depending on role: upload documents one at a time or in bulk (doctor/nurse/admin
only), search across records in natural language and get a cited, redacted answer, and (any
authenticated user) browse the audit log and DLQ.

## Key User Flows

| Flow | What Happens |
|---|---|
| Sign in | `login_page.py` form → `security/auth.py:login()` checks username/password against a hardcoded in-memory user store → sets `st.session_state` → app reruns into the main app |
| Sign out | `logout()` clears session keys → app reruns to login page |
| Single upload | select file(s) → rate-limit check → `ingest_document()` per file → progress/status shown |
| Bulk upload (role-gated) | role check against `get_ingest_allowed_roles()` → rate-limit check → `_process_single_upload_bytes()` per file → per-file result table → audit event logged |
| Search | rate-limit check → input guardrail check → PII pre-filter if query contains a detected entity → vector/keyword search → rerank → Claude-generated answer → output sanitization → answer + citations displayed → audit event logged |
| View audit trail / DLQ | `audit_page.py` reads `AuditLog` rows and `queues/dlq.py` messages, no write actions |

## UI States

| Condition | What Renders |
|---|---|
| Not authenticated | Only the login form; every other page is unreachable (`streamlit_app.py` gate) |
| Login fails | "Invalid username or password." |
| Bulk upload, wrong role | "Access denied. Bulk upload requires one of: doctor, nurse, admin. Your role: {role}" |
| Rate limit exceeded (upload or search) | "Rate limit exceeded... Max 10 [uploads/queries]/minute." |
| Search query blocked by guardrail | "Query blocked: {reason}" |
| Search: PII detected in query | Caption noting which entities were detected and how many chunks the pre-filter matched |
| Search: no results | "No results found. Try a broader query or ingest more documents." |
| DLQ empty | Success message "DLQ is empty" |
| DLQ has messages | Warning with expandable per-message entries |

## APIs Consumed

All calls are direct in-process Python function calls, not HTTP — this whole app (except the
separate ADE extraction service, Feat-0002) runs as one Python process.

| Function | Owning Feature |
|---|---|
| `ingest_document()`, `_process_single_upload_bytes()` (`app/main.py`) | Feat-0001 |
| `get_ingest_allowed_roles()` (`ingestion/metadata/rbac_policy.py`) | Feat-0001 |
| vector/keyword search helpers (`indexing/*`), `rerank()`, `generate_answer()` (`llm/claude_client.py`) | Feat-0003 |
| `login()`, `logout()`, `is_authenticated()`, `current_user()` (`security/auth.py`) | Feat-0005 |
| `filter_results_by_role()` (`security/access_control.py`) | Feat-0005 |
| `check_input()`, `sanitise_output()` (`security/guardrails.py`) | Feat-0005 |
| `log_event()`, `get_audit_trail()` (`security/audit_logger.py`) | Feat-0005 |
| `rate_limiter.is_allowed()` (`app/dependencies.py`) | Feat-0001 |

**Note**: `search_page.py` calls `filter_results_by_role()` directly but does **not** call
`apply_role_mask()`/`secure_results()` — see Feat-0003's BR-06 CRITICAL gap. This page is where
that gap actually manifests to a user.

## State

No Redux-style store — state lives in Streamlit's `st.session_state`, written once at login and
read by every other page.

| Key | Set By | Read By |
|---|---|---|
| `authenticated` (bool) | `login()` / cleared by `logout()` | `streamlit_app.py`'s auth gate |
| `username` (str) | `login()` | `bulk_upload_page.py` (rate limiting), `search_page.py` |
| `role` (str) | `login()` | `bulk_upload_page.py` (access check), `search_page.py` (RBAC filtering) |
| `department` (str) | `login()` | `streamlit_app.py` (sidebar display) |
| `display_name` (str) | `login()` | `streamlit_app.py` (sidebar display) |

## Access Control

**Model**: Real session-based auth (this is the one place in the repo that actually
authenticates). Every page beyond login is gated on `is_authenticated()`; bulk upload additionally
gates on role membership.

| Action | Access Condition | Enforced In |
|---|---|---|
| Any page except login | `is_authenticated()` true | `streamlit_app.py` |
| Bulk upload page | `role ∈ {doctor, nurse, admin}` | `bulk_upload_page.py:69` |
| Search results | `role` matches chunk `allowed_roles` (filter only, masking gap — see Feat-0003) | `search_page.py` via `security/access_control.py` |

## Known Error Scenarios

| Scenario | Error Returned | Root Cause |
|---|---|---|
| Empty username/password | "Please enter both username and password." | `login_page.py` |
| S3 credentials unavailable during upload | Error with AWS SSO login instructions | propagated from `app/main.py` |
| Vector/keyword search backend unavailable | `st.warning`, degrades to whichever mode still works | `search_page.py` catches broadly |

## Testing Expectations

No test coverage exists under `ui/` today — see `AiHarness/skills` and the `frontend-test` skill
for the recommended approach (`streamlit.testing.v1.AppTest`) if adding coverage.

## Forbidden Patterns

- Never add a new backend call from a page without routing search results through the same
  RBAC-filter-then-mask flow other pages assume is happening — see Feat-0003's gap for what
  happens when that's skipped.

## Key Files

- `ui/streamlit_app.py` — router/entrypoint, auth gate, sidebar
- `ui/login_page.py` — login form
- `ui/upload_page.py` — single-file upload
- `ui/bulk_upload_page.py` — role-gated batch upload
- `ui/search_page.py` — search, rerank, LLM answer, citations
- `ui/audit_page.py` — audit trail + DLQ viewer

## Context Routing

| Feature | Load when |
|---|---|
| Feat-0004 | touching any Streamlit page, session-state key, or user-facing flow/copy |
| Feat-0001, Feat-0003, Feat-0005 | touching the backend function a page calls into |

*Open question: is there a plan to route `search_page.py` through `apply_role_mask()`, or should
this UI's direct-call pattern become the model other future callers follow instead (in which case
`search/pipeline.py:secure_results()` would be the thing to remove/update)?*
