---
paths:
  - "app/**/*.py"
  - "db/**/*.py"
  - "ingestion/**/*.py"
  - "workers/**/*.py"
  - "queues/**/*.py"
  - "search/**/*.py"
  - "llm/**/*.py"
  - "indexing/**/*.py"
  - "monitoring/**/*.py"
  - "evaluation/**/*.py"
  - "security/**/*.py"
  - "storage/**/*.py"
  - "mlx_adapter/**/*.py"
  - "ui/**/*.py"
---

# Security Rules

## Project Auth Model

Populated by `onboard.sh`. Read this section before reviewing any access control logic.

| Field | Value |
|-------|-------|
| **Model** | RBAC (role-based), enforced inconsistently across the two entry points. The Streamlit UI (`ui/`) requires a real login; the FastAPI HTTP endpoint (`app/main.py`) does not authenticate the caller at all. |
| **Mechanism** | Streamlit UI: `security/auth.py:login()` checks a username/password against a hardcoded in-memory `_USERS` dict (SHA-256 hash, no salt) and sets `st.session_state["authenticated"]`. FastAPI `POST /ingest/bulk`: no session, token, or JWT check of any kind — the caller's `role` is read directly from a `role` request header (`Header(...)`) and trusted as-is, with no verification that it corresponds to a real logged-in identity. |
| **Access primitive** | `user.role` (single string) checked against per-department allow-lists in `ingestion/metadata/rbac_policy.py` (`_DEPARTMENT_ROLES`, `_INGEST_ALLOWED_ROLES`), applied at query time via `security/access_control.py:filter_results_by_role()`. |
| **Roles / scopes** | `admin`, `doctor`, `nurse`, `cardiologist`, `radiologist`, `billing`, `researcher`. Departments: `general`, `cardiology`, `radiology`, `billing`, `oncology`. |

**Frontend/backend trust boundary gap**: `ui/` performs real authentication before letting a user reach any page, but `app/main.py`'s `POST /ingest/bulk` endpoint has no authentication of its own — it accepts whatever `role` header the caller sends. Treat any new or modified FastAPI endpoint that trusts a client-supplied role/user header without an independent identity check as a SEC-01/SEC-02 finding; it is not covered by the Streamlit login.

## SEC-01: Authentication on endpoints <!-- severity: blocker -->
Every new API endpoint must require authentication unless explicitly intended to be public. Check for security annotations, configuration, or middleware that enforces auth. Compare with similar existing endpoints.

## SEC-02: Authorization and access control <!-- severity: blocker -->
Operations on resources must verify the requesting user has permission to access/modify that specific resource — not just that they are authenticated. Look for missing ownership checks (e.g., user A can modify user B's data). Check role-based access enforcement.

## SEC-03: Input validation <!-- severity: blocker -->
All user-supplied input (request bodies, query params, path params, headers) must be validated before use. Check for: missing validation annotations on request DTOs, missing schema validation, unbounded string lengths, negative numbers where only positive are valid, enum values not checked.

## SEC-04: SQL injection <!-- severity: blocker -->
Database queries must use parameterized queries or ORM criteria — never string concatenation with user input. Check for raw SQL queries built with string interpolation.

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
