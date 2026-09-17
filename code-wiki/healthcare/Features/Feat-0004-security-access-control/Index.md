---
feat_id: Feat-0004
feature: security-access-control
type: backend-service
domain: security
criticality: high
touched_paths:
  - security/
depends_on: [Feat-0002, Feat-0007]
consumed_by: [Feat-0001, Feat-0002, Feat-0005, Feat-0006]
implements: []
tags: [auth, rbac, encryption, audit, guardrails]
---

## Overview

| Field | Value |
|---|---|
| Type | backend-service |
| Package | `security/` |
| Path | `security/*.py` |
| Domain | security |
| Last updated | 2026-09-17 |

## Domain Purpose

The sole enforcement point for who can log in, what a caller's role lets them see, what gets
encrypted, what gets audited, and what unsafe input/output gets blocked — every other feature
that needs an access, encryption, or audit decision calls into this one rather than
implementing its own.

## Invariants

- Role masking (via `ingestion/pii/role_based_masking.py`, called from Feat-0005) is applied
  strictly **after** `filter_results_by_role` — never before. A chunk that fails the RBAC
  filter must never reach the masking step, and a chunk that passes must always be masked
  before being returned to the caller.
- `admin` always passes the chunk-level RBAC filter but is **not** exempt from role-based PII
  masking downstream — admin still cannot see certain clinical entity types.
- An unknown role passed to `apply_role_mask` masks *all* detected tokens (fail-closed default).
- Audit-log writes never block on a DB failure — the file write (`audit.log`) always succeeds
  independently of the DB write.

## Access Control

**Model**: Role-based access control (RBAC), department-scoped — see `security.md`'s Project
Auth Model table for the full picture across the whole repo. This feature is the mechanism, not
the policy: the department→role mapping itself lives in Feat-0002
(`ingestion/metadata/rbac_policy.py`).

| Action | Access Condition | Enforced In |
|---|---|---|
| Log in (Streamlit UI) | username + password match an entry in the hardcoded, in-memory `_USERS` table (SHA256 hash, no salt) | `security/auth.py:login()` |
| Read a retrieved chunk | caller's role ∈ chunk's `allowed_roles` metadata, or caller's role is `admin` | `security/access_control.py:filter_results_by_role()` |
| See a specific PII entity type in a chunk | caller's role not in that entity type's forbidden set | `ingestion/pii/role_based_masking.py:apply_role_mask()` (Feat-0002, called from this feature's intended flow) |

**CRITICAL finding, repeated from Feat-0002**: this feature's auth (`security/auth.py`) is a
Streamlit session-state gate — it has **no relationship at all** to the FastAPI
`/ingest/bulk` endpoint, which reads an unverified `role` header directly. There is no shared
session or token between the two entry points into this system.

## Business Rules

| BR-NN | Rule | Enforced In | Severity |
|---|---|---|---|
| BR-01 | Query-time enforcement order is `filter_results_by_role` → `apply_role_mask`, non-negotiable | `security/access_control.py:14-37`, `ingestion/pii/role_based_masking.py` | CRITICAL |
| BR-02 | Passwords are SHA256-hashed with no salt, in an in-memory dict — not backed by a real user store | `security/auth.py:1-38` | HIGH (prototype-grade auth, see Forbidden Patterns) |
| BR-03 | Input guardrail blocks 14 known prompt-injection/jailbreak regex patterns before a query is processed | `security/guardrails.py:13-31` (`check_input`) | HIGH |
| BR-04 | Output guardrail re-scans and redacts any PII that leaked into an LLM-generated answer | `security/guardrails.py:46-60` (`sanitise_output`) | HIGH |
| BR-05 | Encryption falls back to plaintext passthrough if the `cryptography` package is unavailable, logging an ERROR rather than raising | `security/encryption.py` | HIGH — a silent security downgrade if the dependency is ever missing in an environment |
| BR-06 | Audit events are dual-written (file + DB); a DB failure is a WARNING, never fatal | `security/audit_logger.py:39-49` | MEDIUM |

## Known Error Scenarios

| Scenario | Error Returned | Root Cause |
|---|---|---|
| Bad login credentials | `login()` returns `False`; UI shows "Invalid username or password." | `security/auth.py:45-48` |
| Prompt-injection pattern matched | Query blocked, `GUARDRAIL_BLOCKED` audit event | `security/guardrails.py:check_input()` |
| Encryption/decryption exception | Logged ERROR, plaintext returned as fallback (not raised) | `security/encryption.py:49-50, 62` |
| Audit DB write fails | WARNING logged; the file-based audit record still exists | `security/audit_logger.py:48-49` |

## Testing Expectations

- `tests/unit/test_researcher_role.py` covers RBAC filtering and role-based masking end to end
  (researcher blocked from billing, PII masked but clinical tokens preserved, doctor/nurse see
  unmasked text).
- *Open question: no dedicated test file was found for `security/auth.py` (login/logout/session
  state) or `security/guardrails.py` (injection detection) in isolation.*

## Forbidden Patterns

- Never call `apply_role_mask()` before `filter_results_by_role()` — a dropped chunk must never be masked-and-returned instead of excluded.
- Never treat `security/auth.py`'s in-memory `_USERS` table as production-ready — it is explicitly a prototype (see its own module docstring: "replace with a real DB in production").
- Never assume the FastAPI `role` header (Feat-0002) is backed by this feature's session auth — it is not.

## Key Files

- `security/auth.py` — Streamlit session-state login/logout, hardcoded user store
- `security/access_control.py` — `filter_results_by_role`, the sole query-time RBAC enforcement point
- `security/audit_logger.py` — `log_event`, `get_audit_trail` — dual-write audit trail (file + DB)
- `security/encryption.py` — Fernet (AES + HMAC) PHI encryption, auto-generated key with plaintext fallback
- `security/guardrails.py` — `check_input` (prompt-injection detection), `sanitise_output` (final PII scrub)

## Context Routing

| Feature | Load when |
|---|---|
| Feat-0002 (Document Ingestion Pipeline) | changing `_DEPARTMENT_ROLES`/`_INGEST_ALLOWED_ROLES`, which this feature's RBAC check reads |
| Feat-0005 (Semantic Search & Indexing) | changing the query-time call order or the masking rules |

| Workflow | Sections to load |
|---|---|
| Add a new role | Access Control, Business Rules |
| Close the `/ingest/bulk` header-trust gap | Access Control (both this file and Feat-0002's) |
