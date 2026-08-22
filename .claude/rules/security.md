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
| **Model** | Split, and inconsistent: session-based login gates the Streamlit UI; the internal FastAPI services behind it require **no authentication at all** and trust whatever role/identity the caller sends as a header. |
| **Mechanism** | The UI checks credentials in `security/auth.py::login()` against a hardcoded in-memory user table (SHA-256 password hashes, no real user DB, no password reset/expiry) and stores the result in `st.session_state` — no cookie, token, or JWT is ever issued. The FastAPI layer verifies nothing: `POST /ingest/bulk` (`app/main.py`) reads `role`, `uploader_id`, `patient_id`, `department` as plain, unsigned HTTP headers and acts on them as-is; `llm/ade_api.py`'s `/extract` and `/health` have no auth check whatsoever. |
| **Access primitive** | A self-asserted role string (plus a `department` string), not a verified identity or resource-ownership check. Enforcement is post-hoc: `security/access_control.py::filter_results_by_role` filters retrieved chunks by matching the caller-supplied role against each chunk's `allowed_roles` metadata (set at ingest time by `ingestion/metadata/rbac_policy.py`), and `rbac_policy.get_ingest_allowed_roles()` gates who may call bulk ingest. There is no per-user resource-ownership model anywhere in the codebase. |
| **Roles / scopes** | `admin`, `doctor`, `nurse`, `radiologist`, `billing` are the login-table roles in `security/auth.py`. `ingestion/metadata/rbac_policy.py` additionally recognizes `cardiologist` and `researcher` for chunk-access filtering. `admin` has universal read access to chunk metadata but is still subject to downstream role masking — not a full bypass. |

This is a single Python codebase, not a split frontend/backend repo — `ui/` (Streamlit) is the "frontend" and is the *only* place login/role gating exists. Everything else (`app/`, `llm/`, `ingestion/`, `security/`, etc.) is called in-process or over an internal, unauthenticated HTTP call. Treat any new FastAPI endpoint as unauthenticated by default (SEC-01 currently fails repo-wide for `app/main.py` and `llm/ade_api.py`), and treat any change to `ui/` as the sole place that can add or break login/role enforcement — there is no second gate downstream.

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
