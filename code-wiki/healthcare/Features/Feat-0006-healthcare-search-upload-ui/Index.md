---
feat_id: Feat-0006
feature: healthcare-search-upload-ui
type: frontend-feature
domain: user-interface
criticality: high
touched_paths:
  - ui/
depends_on: [Feat-0001, Feat-0002, Feat-0003, Feat-0004, Feat-0005, Feat-0007]
consumed_by: []
implements: []
tags: [ui, streamlit, rag, rbac]
---

## Overview

| Field | Value |
|---|---|
| Type | frontend-feature |
| Package | `ui/` |
| Path | `ui/*.py` |
| Domain | user-interface |
| Last updated | 2026-09-17 |

Note: this is **not** a JS/TS/React frontend. It is a Streamlit app — server-rendered Python,
running in the same process as the rest of the application, calling other features' Python
functions directly rather than fetching JSON from a separate API for most flows.

## Domain Purpose

The single interface clinical and administrative staff use to log in, upload documents, search
the ingested corpus with a cited LLM answer, and review the audit trail / dead-letter queue —
the place every other feature's work is actually seen and used.

## What This Does for the User

Lets an authenticated hospital-staff user (doctor, nurse, admin, radiologist, cardiologist,
billing, or researcher) upload clinical documents for ingestion, ask natural-language questions
against the ingested corpus and get a cited answer, and — for staff with the right role — audit
what's happened and inspect failed ingestion jobs.

## Key User Flows

| Flow | What Happens |
|---|---|
| Log in | Username/password checked against `security.auth`'s hardcoded user table; on success, role/department/display name are set in `st.session_state` and the app reruns into the authenticated shell |
| Upload a single document | File + uploader/patient/department fields → rate-limit check → `app.main.ingest_document()` called directly (in-process) → success/failure shown per file |
| Bulk upload (≤50 files) | Same as above, gated to `doctor`/`nurse`/`admin` roles → `app.main._process_single_upload_bytes()` called directly per file, **not** via the `POST /ingest/bulk` HTTP endpoint (see open question below) |
| Search | Query → rate limit → prompt-injection guardrail → PII pre-filter (Top-D) → hybrid vector+BM25 retrieval → RRF merge → cross-encoder re-rank → RBAC filter + PII mask → Claude-generated cited answer → output guardrail |
| View audit trail / DLQ | `security.audit_logger.get_audit_trail()` and `queues.dlq.list_messages()`, filterable by `doc_id` |

## UI States

| Condition | What Renders |
|---|---|
| Not authenticated | Login form only; app gate in `streamlit_app.py` blocks all pages |
| Invalid login | "Invalid username or password." |
| Rate limit exceeded (upload or search) | Explicit rate-limit error, logged as an audit event |
| Caller lacks an ingest-allowed role, on Bulk Upload | "Access denied. Bulk upload requires one of: {roles}." — page content is blocked, not hidden |
| Search query blocked by guardrail | "Query blocked: {reason}", logged as `GUARDRAIL_BLOCKED` |
| PII detected in query | Caption noting pre-filtering to N matching chunks |
| No search results (post-RBAC-filter or genuinely empty index) | "No results found." — these two cases are indistinguishable to the user, see Feat-0005 |
| DLQ empty | "DLQ is empty — no failed documents." |

## APIs Consumed

| Method | Path / Call | Owning `Feat-NNNN` |
|---|---|---|
| *(in-process call, not HTTP)* `app.main.ingest_document()` | — | Feat-0002 |
| *(in-process call, not HTTP)* `app.main._process_single_upload_bytes()` | — | Feat-0002 |
| *(in-process calls)* `security.auth.*`, `security.access_control.filter_results_by_role`, `security.guardrails.*`, `security.audit_logger.*` | — | Feat-0004 |
| *(in-process calls)* `indexing.embeddings.embed_query`, `indexing.chroma_store.query`, `indexing.opensearch_index.keyword_search*`, `indexing.reranker.rerank`, `indexing.pii_entity_index.get_chunk_ids_for_entities` | — | Feat-0005 |
| *(in-process call)* `llm.claude_client.generate_answer` | — | Feat-0003 |
| POST /ingest/bulk | — | Feat-0002 — **defined but not called by this UI**; only reachable externally |

## State

Not a JS store — Streamlit's `st.session_state`, set by `security.auth.login()`:

| Key | Shape |
|---|---|
| `authenticated` | bool |
| `username` | str |
| `role` | one of `admin`, `doctor`, `nurse`, `radiologist`, `cardiologist`, `billing`, `researcher` |
| `department` | str |
| `display_name` | str |

Cleared entirely by `security.auth.logout()`. Process-scoped — an app restart or scale-out logs every user out, since there is no persistent session store.

## Safe vs Dangerous Changes

### Safe
- Adding a new page to `PAGES` in `streamlit_app.py` for an existing role.
- Changing rate-limit thresholds.

### Dangerous — Requires Review
| Change | Risk | Why |
|---|---|---|
| Adding role-gating logic ad hoc per-page | Inconsistent access control across pages | Today only `bulk_upload_page.py` gates on role; `upload_page.py` does not — confirm this is intentional before copying the pattern |
| Changing the bulk-upload code path to go through `POST /ingest/bulk` over HTTP instead of the direct in-process call | Introduces a real network hop and the endpoint's unauthenticated-header issue (Feat-0002) into a flow that's currently safe by virtue of running in-process as an already-authenticated session | Would need the header-trust gap fixed first |

### Human Escalation Required
- Any change to which roles can access which page — this is a real authorization boundary, not styling.

## Known Error Scenarios

| Scenario | Error Returned | Root Cause |
|---|---|---|
| AWS credentials unavailable during upload | "AWS credentials are unavailable or expired. Run aws sso login..." | Surfaced verbatim from Feat-0002's `ingest_document()` |
| Vector or keyword search backend unavailable | "Vector search unavailable: {e}" / "Keyword search unavailable: {e}", falls back to the other retrieval mode | `ui/search_page.py` |
| Worker threads fail to start | Not reported to the user — silent | `upload_page.py`/`bulk_upload_page.py` worker-thread init has no startup confirmation |

## Testing Expectations

- *Open question: no dedicated test file was found for `ui/` pages. Given this is server-rendered Python (not a component tree), tests would call page render/helper functions directly rather than mount anything — see `.claude/skills/frontend-test/SKILL.md` for this repo's adapted approach.*

## Forbidden Patterns

- Never display a chunk's content without it having passed through the RBAC filter + PII mask sequence — currently this UI reimplements that sequence itself rather than calling a shared function (see Feat-0005's architectural finding); any UI change here must preserve the exact order.
- Never let `audit_page.py`'s `doc_id` filter be treated as an access-control boundary — it isn't one today (any authenticated user can view any document's audit trail by `doc_id`), so don't build a feature that assumes otherwise.

## Key Files

- `ui/streamlit_app.py` — entry point, auth gate, page routing, sidebar
- `ui/login_page.py` — login form
- `ui/upload_page.py` — single-file upload (no role gate)
- `ui/bulk_upload_page.py` — batch upload (role-gated), calls Feat-0002's function directly, bypassing the HTTP endpoint
- `ui/search_page.py` — full query pipeline: rate limit, guardrails, PII pre-filter, hybrid retrieval, re-rank, RBAC+mask, LLM answer
- `ui/audit_page.py` — audit trail + DLQ viewer, unscoped by caller role

## Context Routing

| Feature | Load when |
|---|---|
| Feat-0002 (Document Ingestion Pipeline) | changing upload flows or ingest function signatures |
| Feat-0004 (Security & Access Control) | changing auth, guardrails, or the RBAC/masking call sequence |
| Feat-0005 (Semantic Search & Indexing) | changing retrieval, ranking, or the RBAC+mask call site itself |

| Workflow | Sections to load |
|---|---|
| Add role-based gating to a new page | Key User Flows, Safe vs Dangerous Changes |
| Fix the bulk-upload endpoint bypass | APIs Consumed, Safe vs Dangerous Changes |
