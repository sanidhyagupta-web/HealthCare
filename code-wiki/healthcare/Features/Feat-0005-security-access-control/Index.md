---
feat_id: Feat-0005
feature: security-access-control
type: shared-library
domain: security
criticality: high
touched_paths:
  - security/
depends_on: []
consumed_by: [Feat-0001, Feat-0003, Feat-0004]
implements: []
tags: [auth, rbac, encryption, audit, guardrails]
---

## Overview

| Type | Package | Path | Domain | Last updated |
|---|---|---|---|---|
| shared-library | (single package) | `security/` | Auth, RBAC, encryption, audit logging, LLM guardrails | 2026-09-03 |

## Domain Purpose

The cross-cutting security primitives every other feature calls into: Streamlit session login,
query-time RBAC filtering, PHI encryption, audit logging, and input/output LLM guardrails. Closely
related but *not* owned here: `ingestion/pii/role_based_masking.py` (owned by
[Feat-0001](../Feat-0001-document-ingestion-pipeline/Index.md), applies per-role token masking)
and `ingestion/metadata/rbac_policy.py` (also Feat-0001, defines the role/department policy this
library enforces).

## Entities Owned

| Entity | Represents |
|---|---|
| [audit_log](../../Schemas/schemas.md#audit_log) | Every security-relevant event: login, ingest, search, rate-limit hits, guardrail blocks |
| [pii_entity_index](../../Schemas/schemas.md#pii_entity_index-datapii_entity_indexjson) | SHA-256 hashes of detected PII entities, for query-time patient-scoped pre-filtering |
| [pii_doc_index](../../Schemas/schemas.md#pii_doc_index-datapii_doc_indexjson) | doc↔chunk mapping used to expand a patient-name match to the whole document |

## Invariants

- Encryption key resolution order: `ENCRYPTION_KEY` env var → `.encryption_key` file → generated
  on first run (`security/encryption.py`).
- Audit events are always written to `logs/audit.log` first; the database write is best-effort
  (failure logged as WARN, never blocks the caller).
- `apply_role_mask()` (Feat-0001, but security-critical) never mutates its input chunk.

## Access Control

**Model**: RBAC (role-based), enforced inconsistently across the two entry points into this
system — see `.claude/rules/security.md` for the full statement. In short:
`ui/` performs real login; `app/main.py`'s `POST /ingest/bulk` does not authenticate at all, only
checking a client-supplied `role` header against an allow-list.

| Action | Access Condition | Enforced In |
|---|---|---|
| Streamlit login | username/password matches a hardcoded in-memory user record | `security/auth.py:login()` |
| Query-time chunk retrieval | `role ∈ chunk.allowed_roles` or `role == "admin"` | `security/access_control.py:filter_results_by_role()` |
| LLM input | query doesn't match one of 14 injection/jailbreak regex patterns | `security/guardrails.py:check_input()` |
| LLM output | any PII the model leaked gets redacted before display | `security/guardrails.py:sanitise_output()` |
| Ingest endpoint | `role` header ∈ `{doctor, nurse, admin}` — **the header itself is never verified against a real identity** | `app/main.py:168`, backed by Feat-0001's `rbac_policy.py` |

## Business Rules

| BR | Rule | Enforced In | Severity |
|---|---|---|---|
| BR-01 | `login()` compares SHA-256(password) with **no salt** against 5 hardcoded demo accounts | `security/auth.py` | CRITICAL (acceptable only if this is genuinely demo-only, not production auth) |
| BR-02 | `filter_results_by_role()` is the sole RBAC gate at query time; admin bypasses the allow-list check but the design intends masking to still apply after | `security/access_control.py` | CRITICAL |
| BR-03 | Unknown role passed to masking → mask all detected entity types (fail-safe) | `ingestion/pii/role_based_masking.py` (Feat-0001) | HIGH |
| BR-04 | `check_input()` blocks 14 known injection/jailbreak patterns before any query reaches the LLM | `security/guardrails.py` | HIGH |
| BR-05 | `sanitise_output()` re-scans the LLM's own answer for PII before display, independent of ingest-time redaction | `security/guardrails.py` | HIGH |
| **BR-06** | **`POST /ingest/bulk` trusts a client-supplied `role` header with zero identity verification** | `app/main.py:156,168` | **CRITICAL — real gap, not hypothetical; any caller can claim any role** |
| BR-07 | Encryption falls back to plaintext passthrough (with an ERROR log) if the `cryptography` library or key is unavailable, rather than failing the request | `security/encryption.py` | CRITICAL — silent PHI exposure risk |
| BR-08 | Rate limiting is in-process (`app/dependencies.py`, token bucket, 10/min default) — resets on restart, and does not coordinate across multiple processes/workers | `app/dependencies.py` | MEDIUM |

## External Integrations

| System | Trigger | What Happens |
|---|---|---|
| SQLite (`audit_log` table) | every logged event | best-effort write, file log is authoritative |
| `cryptography` (Fernet) | every PHI encrypt/decrypt call | AES-128-CBC + HMAC-SHA256 |

## API Endpoints

None — this is a shared library, called in-process by Feat-0001 (`app/main.py`, `workers/pii_worker.py`), Feat-0003 (`search/pipeline.py`), and Feat-0004 (every `ui/` page except plain rendering).

## Safe vs Dangerous Changes

### Safe
- Adding a new injection/jailbreak regex pattern to `guardrails.py:check_input()`.
- Adding a new audit `event_type`.

### Dangerous — Requires Review
| Change | Risk | Why |
|---|---|---|
| Changing `filter_results_by_role()`'s signature or return shape | Breaks every caller (Feat-0001, Feat-0003, Feat-0004, `evaluation/run_eval.py`) simultaneously | 5+ call sites, no shared interface/contract test |
| Removing the encryption plaintext-fallback without an explicit failure mode | Currently the "safe" thing to remove, but removing it naively could turn a soft PHI-exposure bug into a hard outage — needs a deliberate migration, not a one-line change | see BR-07 |

### Human Escalation Required
- **Any change to how `/ingest/bulk` authenticates** — this is the CRITICAL gap (BR-06); fixing it changes a real security boundary, not an implementation detail.
- **Deciding whether `auth.py`'s hardcoded users are acceptable for the deployment target** — if this is heading to production rather than staying a demo, this needs a real user store and salted/adaptive hashing (bcrypt/argon2), not a local code change.

## Known Error Scenarios

| Scenario | Error Returned | Root Cause |
|---|---|---|
| Wrong username/password | `login()` returns `False`, UI shows "Invalid username or password." | expected |
| `cryptography` unavailable or decrypt fails | plaintext passthrough (encrypt) or original ciphertext returned (decrypt), both logged as ERROR | fallback design in `encryption.py` |
| Role not in chunk's `allowed_roles`, not admin | empty result list, no error | `filter_results_by_role()` |
| Query matches an injection pattern | query rejected, "Your query contains disallowed content…", `GUARDRAIL_BLOCKED` audit event | `check_input()` |
| Audit DB write fails | WARN logged, file write still succeeds | `audit_logger.py` — no circuit breaker |

## Testing Expectations

- `tests/unit/test_researcher_role.py` covers `apply_role_mask()`, `filter_results_by_role()`, and
  `secure_results()` end-to-end for the researcher role specifically.
- No test coverage found for: `login()`/password hashing, `guardrails.py` (`check_input`/
  `sanitise_output`), `encryption.py`'s fallback behavior, or the `/ingest/bulk` header-trust gap
  itself.

## Forbidden Patterns

- Never log a raw password, encryption key, or unredacted PHI value at any log level.
- Never treat a client-supplied `role` header as verified identity without also checking there is
  actually a real auth mechanism behind it (today, there isn't, for the ingest endpoint — BR-06).

## Key Files

- `security/auth.py` — Streamlit login/logout/session helpers, hardcoded demo user store
- `security/access_control.py` — `filter_results_by_role()`
- `security/encryption.py` — Fernet encrypt/decrypt with plaintext fallback
- `security/audit_logger.py` — `log_event()`, `get_audit_trail()`
- `security/guardrails.py` — `check_input()`, `sanitise_output()`
- (Related, owned by Feat-0001) `ingestion/pii/role_based_masking.py`, `ingestion/metadata/rbac_policy.py`

## Context Routing

| Feature | Load when |
|---|---|
| Feat-0005 | touching auth, RBAC enforcement, encryption, audit logging, or LLM guardrails |
| Feat-0001 | touching the ingest endpoint's role trust boundary, or the masking/policy modules it owns |
| Feat-0003 | touching where `filter_results_by_role()`/masking is (or isn't) called during search |

*Open question: is `/ingest/bulk` meant to be reachable only from trusted internal callers (in
which case the missing auth may be an accepted network-boundary decision), or is it exposed more
broadly? This determines whether BR-06 is a documentation gap or a real vulnerability.*

*Open question: is the audit trail (`get_audit_trail(doc_id)`) intended to be readable by any
authenticated user regardless of role, or should it itself be role-gated?*
