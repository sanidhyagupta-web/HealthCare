---
feat_id: Feat-0006
feature: security
type: backend-service
domain: auth-rbac-audit
criticality: high
touched_paths:
  - security/auth.py
  - security/access_control.py
  - security/audit_logger.py
  - security/encryption.py
  - security/guardrails.py
depends_on: [platform, app]
consumed_by: [ui, app, workers, search]
implements: []
tags: [auth, rbac, audit, encryption, guardrails]
---

## Overview

| Type | Package | Path | Domain | Last updated |
|---|---|---|---|---|
| backend-service | `security` | `security/` | Session auth, RBAC filter, audit log, PHI encryption, LLM guardrails | 2026-09-17 (initial scan) |

## Domain Purpose

Everything the system calls "security": Streamlit session login, the one function that RBAC-filters
search results, dual-write (file + DB) audit logging, Fernet-based PHI encryption, and prompt-injection
/ output-PII guardrails around the LLM call.

## Entities Owned

- [audit_log](../../Schemas/schemas.md#audit_log) — append-only audit trail

## Invariants

- All authentication state lives in `st.session_state`; there is no server-side session store.
- `filter_results_by_role()` never skips masking for `admin` — admin gets universal *metadata*
  visibility only, not an exemption from downstream PII masking (see [[search]] for whether that
  downstream step actually runs today).
- Encryption failures degrade to returning plaintext/ciphertext unchanged rather than raising
  (`security/encryption.py:49-50, 61-62`) — a deliberate availability-over-confidentiality choice,
  worth confirming is still intended.

## Access Control

**Model**: Role-based access control (RBAC), self-asserted rather than cryptographically verified —
see `.claude/rules/security.md` for the full project-wide statement. Roles:
`admin`, `doctor`, `nurse`, `cardiologist`, `radiologist`, `billing`, `researcher`.

| Action | Access Condition | Enforced In |
|---|---|---|
| Any Streamlit page render | `is_authenticated()` true | `security/auth.py:64`, gated once at `ui/streamlit_app.py:19-22` |
| Login | username/password match the hardcoded prototype store (SHA-256, no salt) | `security/auth.py:45-56` |
| Chunk read at query time | `user_role ∈ chunk.metadata.allowed_roles` or `user_role == "admin"` | `security/access_control.py:14-37` |
| LLM query input | passes `check_input()` prompt-injection/jailbreak check | `security/guardrails.py`, called at `ui/search_page.py:141` |
| LLM output shown to user | passes `sanitise_output()` PII scrub | `security/guardrails.py`, called at `ui/search_page.py:186` |

## Business Rules

| BR-NN | Rule | Enforced In | Severity |
|---|---|---|---|
| BR-01 | `filter_results_by_role` is the **sole** RBAC enforcement point for chunk retrieval — no other code path filters by role | `security/access_control.py:14-37` | CRITICAL |
| BR-02 | Passwords are SHA-256 hashed with **no salt** against a hardcoded 5-user prototype store | `security/auth.py:7-38` | HIGH |
| BR-03 | No login-attempt throttling or account lockout exists | absence, `security/auth.py` | MEDIUM |
| BR-04 | `ui/audit_page.py` shows the full audit trail to **any authenticated user**, regardless of role | absence — no role check in `audit_page.py` | HIGH |
| BR-05 | `ui/upload_page.py` (single-file ingest) has no ingest-role check, unlike `bulk_upload_page.py` | absence, `ui/upload_page.py` | HIGH |
| BR-06 | Encryption key falls back to a plaintext `.encryption_key` file on disk if not set via env | `security/encryption.py` | MEDIUM |
| BR-07 | Audit DB write failures are swallowed (logged as warning); the file write still succeeds | `security/audit_logger.py:48-49` | LOW |

## External Integrations

None — this module has no outbound third-party calls of its own (encryption/audit are local).

## Safe vs Dangerous Changes

### Safe
- Adding a new audit `event_type`.
- Tightening `check_input()`'s jailbreak regex patterns.

### Dangerous — Requires Review
| Change | Risk | Why |
|---|---|---|
| Changing `filter_results_by_role`'s admin exception | RBAC bypass or over-restriction | It's the sole enforcement point; every caller assumes this exact semantics |
| Migrating password hashing away from raw SHA-256 | Should be done, but changes the login flow and the hardcoded user store format | No migration path exists today; this is prototype-grade auth, not production |
| Removing the plaintext-fallback branches in `encryption.py` | Could turn a soft failure into a hard outage | Currently a deliberate availability choice — confirm before hardening it into a raise |

### Human Escalation Required
- Adding real session security (CSRF/session signing) or auth hardening (salted hashes, lockout, MFA) — currently none of this exists and it's a prototype user store, not a real auth system.
- Restricting `ui/audit_page.py` to admin-only, since today every authenticated user can see every other user's queries and document accesses.

## Known Error Scenarios

| Scenario | Error Returned | Root Cause |
|---|---|---|
| Bad login | generic "Invalid username or password." | `security/auth.py:45-47`, no distinction between unknown user and wrong password (reasonable) |
| Guardrail blocks a query | UI error + `GUARDRAIL_BLOCKED` audit event | `security/guardrails.py:check_input()` |
| Rate limit exceeded | UI error + `RATE_LIMITED` audit event | `app/dependencies.py:RateLimiter`, checked before search/upload |
| Encryption unavailable | logs ERROR, returns plaintext unchanged | `security/encryption.py:49-50` |
| Audit DB write fails | logs warning, continues (file write unaffected) | `security/audit_logger.py:48-49` |

## Testing Expectations

- `tests/unit/test_researcher_role.py` exercises `filter_results_by_role` directly with fixture data.
- *Open question: is there any test coverage for `auth.py`'s login/session logic, or for the guardrail functions?*

## Forbidden Patterns

- Never add a second RBAC filtering function — `filter_results_by_role` must remain the only one.
- Never treat a caller-supplied role/header as verified identity (see [[app]]'s BR-03).

## Key Files

- `security/auth.py` — session login, hardcoded prototype user store
- `security/access_control.py` — `filter_results_by_role()`, the sole RBAC gate
- `security/guardrails.py` — `check_input()` (prompt injection), `sanitise_output()` (PII scrub)
- `security/audit_logger.py` — dual-write (file + `audit_log` table) event logging
- `security/encryption.py` — Fernet PHI encryption, key from env or `.encryption_key` file

## Context Routing

| Feature | Load when |
|---|---|
| Feat-0006-security | touching login, RBAC filtering, audit logging, encryption, or guardrails |

| Workflow | Sections to load |
|---|---|
| Any auth/session change | Access Control, Business Rules BR-02/BR-03, Human Escalation Required |
| Investigating an audit-trail question | Entities Owned, Known Error Scenarios |
