---
paths:
  - "**" # <!-- CUSTOMIZE: glob pattern for your backend repo -->
  - "**" # <!-- CUSTOMIZE: glob pattern for your frontend repo -->
---

# Security Rules

## Project Auth Model

Populated by `onboard.sh`. Read this section before reviewing any access control logic.

| Field | Value |
|-------|-------|
| **Model** | Role-based access control (RBAC). There is no token/session auth layer on the API — the FastAPI `POST /ingest/bulk` endpoint trusts a self-asserted `role` request header with no signature or session verification behind it (see `app/main.py`). Treat any endpoint that trusts a caller-supplied role or user-id header as unauthenticated until a real verification step is added. |
| **Mechanism** | Two different, disconnected mechanisms: (1) the Streamlit UI logs in via `security/auth.py:login()`, which checks a hardcoded prototype user store (SHA-256 password hashes, no salt) and stores `role`/`department`/`username` in `st.session_state`; (2) the FastAPI bulk-ingest endpoint (`app/main.py:bulk_ingest`) reads `role`/`uploader_id`/`patient_id`/`department` directly from request headers with no verification that the caller is who they claim to be. |
| **Access primitive** | A `role` string, checked in two places: ingest-time (`ingestion/metadata/rbac_policy.py:get_ingest_allowed_roles()` — which roles may submit documents) and query-time (`security/access_control.py:filter_results_by_role()` — which per-chunk `allowed_roles` metadata, written at ingest by the PII worker from `rbac_policy.py`'s department→role map, the caller's role is allowed to see). `admin` has universal metadata access but is **not** exempt from PII/role masking downstream (see `skills/access-control.md` and `skills/pii-masking.md`). |
| **Roles / scopes** | `admin`, `doctor`, `nurse`, `cardiologist`, `radiologist`, `billing`, `researcher` — defined in `ingestion/metadata/rbac_policy.py` (department→role map) and the prototype user store in `security/auth.py`. Roles are plain strings, not an enum; adding one means updating `rbac_policy.py`, never hardcoding a role list elsewhere. |
| **Enforcement point** | Ingest submission: `app/main.py:bulk_ingest` header check against `get_ingest_allowed_roles()`. Query-time: `security/access_control.py:filter_results_by_role`, which must run **before** the LLM sees any chunk and before PII masking (see the non-negotiable call order in `skills/access-control.md`). Neither point authenticates the caller — both trust a role the caller supplies. |

**Frontend auth note.** There is no separate frontend framework — the only UI is a single-process Streamlit app (`ui/*.py`). "Frontend auth" is Streamlit's own `st.session_state`, checked per-page (e.g. `is_authenticated()` in `security/auth.py`); it has no relationship to the FastAPI bulk-ingest endpoint's header-based role, which is reachable directly over HTTP without going through the Streamlit login at all. When reviewing changes to `ui/*.py`, verify pages gate on `is_authenticated()`/role before rendering PHI-bearing content. When reviewing changes to `app/main.py` or other HTTP endpoints, do not assume the `role`/`uploader_id` headers are trustworthy — flag any authorization decision based on them as it stands today (SEC-01/SEC-02), since nothing currently prevents a caller from asserting `role: admin`.

## SEC-01: Authentication on endpoints <!-- severity: blocker -->
Every new API endpoint must require authentication unless explicitly intended to be public. Check for security annotations, configuration, or middleware that enforces auth. Compare with similar existing endpoints.

## SEC-02: Authorization and access control <!-- severity: blocker -->
Operations on resources must verify the requesting user has permission to access/modify that specific resource — not just that they are authenticated. Look for missing ownership checks (e.g., user A can modify user B's data). Check role-based access enforcement.

## SEC-03: Input validation <!-- severity: blocker -->
All user-supplied input (request bodies, query params, path params, headers) must be validated before use. Check for: missing validation annotations on request DTOs, missing schema validation, unbounded string lengths, negative numbers where only positive are valid, enum values not checked.

## SEC-04: SQL injection <!-- severity: blocker -->
Database queries must use parameterized queries or ORM criteria — never string concatenation with user input. Check for raw SQL queries built with string interpolation.

<!-- CUSTOMIZE: Replace examples below with your language/ORM's patterns -->
**Bad**: `@Query("SELECT * FROM users WHERE name = '" + name + "'")`
**Good**: `@Query("SELECT u FROM User u WHERE u.name = :name")`

## SEC-05: Secrets and credentials <!-- severity: blocker -->
No API keys, passwords, tokens, or secrets hardcoded in source code, committed config files, or log statements. Check for: hardcoded strings that look like keys/tokens, credentials in config that aren't environment variable references, secrets logged at any level.

## SEC-06: XSS prevention <!-- severity: blocker -->
User-supplied content rendered in the UI must be sanitized or escaped. Avoid injecting user input as raw HTML. Check that user input displayed in the UI goes through the framework's default escaping and is not injected as raw HTML.

## SEC-07: Sensitive data exposure <!-- severity: suggestion -->
API responses should not include sensitive fields unnecessarily (passwords, tokens, SSNs, internal IDs). Check that DTOs exclude sensitive entity fields. Verify that error responses don't leak stack traces, internal paths, or database details.

## SEC-08: CORS and request origin <!-- severity: suggestion -->
If the PR modifies CORS configuration, verify allowed origins are specific (not `*` in production). Check that CORS is not accidentally widened.

## SEC-09: File upload safety <!-- severity: blocker -->
If the PR handles file uploads, verify: file type validation (not just extension — check content type), file size limits, sanitized file names (no path traversal), storage in a safe location, and virus scanning if applicable.

## SEC-10: Rate limiting and abuse prevention <!-- severity: suggestion -->
Public-facing or expensive endpoints (login, search, report generation, file upload) should have rate limiting. Check if the new endpoint is a candidate for rate limiting based on its cost and exposure.
