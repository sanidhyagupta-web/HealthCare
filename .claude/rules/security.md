---
paths:
  - "app/**/*.py"
  - "db/**/*.py"
  - "ingestion/**/*.py"
  - "search/**/*.py"
  - "security/**/*.py"
  - "storage/**/*.py"
  - "workers/**/*.py"
  - "queues/**/*.py"
  - "llm/**/*.py"
  - "indexing/**/*.py"
  - "monitoring/**/*.py"
  - "scripts/**/*.py"
  - "ui/**/*.py"
---

# Security Rules

## Project Auth Model

Populated by `onboard.sh`. Read this section before reviewing any access control logic.

| Field | Value |
|-------|-------|
| **Model** | Role-based access control (RBAC), department-scoped. No per-resource ownership checks — access is entirely a function of the caller's `role` string and the department the data belongs to. |
| **Mechanism** | Two independent mechanisms, not one: (1) the Streamlit UI (`ui/streamlit_app.py`) gates on `security.auth.is_authenticated()` — a session-state flag set by `security/auth.py`'s `login()` against an in-memory, hardcoded user table (`_USERS`, sha256-hashed passwords, no real user store/DB). (2) The FastAPI bulk-ingest endpoint (`POST /ingest/bulk` in `app/main.py`) does **not** authenticate the caller at all — it trusts a client-supplied `role` HTTP header verbatim and only checks that header's value against an allowlist. Any caller can set that header to `"admin"` and pass. Treat this endpoint as effectively unauthenticated when reviewing it. |
| **Access primitive** | The `role` string (e.g. `"doctor"`, `"nurse"`), checked in two places: at ingest, `ingestion/metadata/rbac_policy.get_ingest_allowed_roles()` gates who may submit documents; at query time, each retrieved chunk carries an `allowed_roles` list in its metadata (written at ingest by `ingestion/metadata/rbac_policy.get_allowed_roles(department)`), and `security/access_control.filter_results_by_role()` drops any chunk whose `allowed_roles` doesn't contain the caller's role (admin always passes). A second layer, `ingestion/pii/role_based_masking.py`, additionally redacts specific PII entity types per role (e.g. `researcher` never sees `PATIENT_NAME`/`MRN` even for chunks it's allowed to read). |
| **Roles / scopes** | `admin`, `doctor`, `nurse`, `radiologist`, `cardiologist`, `billing`, `researcher` — the department → allowed-roles mapping is the single source of truth in `ingestion/metadata/rbac_policy.py`'s `_DEPARTMENT_ROLES`; only `doctor`, `nurse`, `admin` may submit documents for ingestion (`_INGEST_ALLOWED_ROLES`). |

**Frontend auth note:** There is no separate frontend service or session/token boundary between "frontend" and "backend" here — the Streamlit app in `ui/` runs the same Python process and reads `st.session_state` directly; it is not calling an authenticated API on the caller's behalf. The FastAPI app in `app/main.py` is a second, independent entry point (used for bulk/batch ingestion) that does not share the Streamlit session and, per SEC-01 below, does not actually authenticate its caller — flag any new endpoint added there that continues this pattern.

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
