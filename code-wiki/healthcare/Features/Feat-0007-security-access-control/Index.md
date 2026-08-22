---
feat_id: Feat-0007
feature: security-access-control
type: shared-library
domain: security
criticality: high
touched_paths:
  - security/auth.py
  - security/access_control.py
  - security/audit_logger.py
  - security/encryption.py
  - security/guardrails.py
  - ingestion/metadata/rbac_policy.py
  - ingestion/pii/role_based_masking.py
depends_on: []
consumed_by: [Feat-0003-document-ingestion, Feat-0004-pipeline-workers, Feat-0005-semantic-search-qa, Feat-0006-streamlit-ui]
implements: []
tags: [security, rbac, audit, encryption, guardrails]
---

## Overview

| | |
|---|---|
| Type | shared-library |
| Package | `security/` (plus `ingestion/metadata/rbac_policy.py` and `ingestion/pii/role_based_masking.py`, the RBAC/masking policy tables this library's functions read) |
| Path | `security/*.py` |
| Domain | Every access-control, audit, encryption, and LLM-guardrail primitive in the repo |
| Last updated | initial scan |

## Domain Purpose

The cross-cutting security layer consumed by nearly every other feature: session login for the
UI, post-retrieval RBAC filtering, PII/PHI encryption, audit logging, and input/output guardrails
around the LLM call. See [[../../rules/security.md]] (repo-level, not part of this tree) for the
full auth-model writeup this scan fed into.

## Entities Owned

- `audit_log` → [[Schemas/schemas.md#audit_log]]

## Invariants

- RBAC filtering (`filter_results_by_role`) must run before role masking (`apply_role_mask`) — enforced by call order in [[Feat-0005-semantic-search-qa]], not by anything inside this library itself.
- `admin` bypasses the RBAC chunk-visibility filter but is **still** subject to role masking — there is no full bypass anywhere in this library.
- An unrecognized role masks every detected entity — the masking table's default is deny, not allow.
- Session identity (Streamlit) is immutable once authenticated, until an explicit `logout()`.

## Access Control

**Model**: role-based, and — repo-wide — **entirely self-asserted with no cryptographic identity
verification**. See the full writeup and file:line citations in `.claude/rules/security.md`'s
Project Auth Model table; this section summarizes what lives specifically in this library.

| Action | Access Condition | Enforced In |
|---|---|---|
| Streamlit login | username/password checked against a hardcoded in-memory table (SHA-256 hashes) | `security/auth.py::login()` |
| Streamlit page access | `is_authenticated()` session flag | `security/auth.py`, called from [[Feat-0006-streamlit-ui]] |
| Document ingest | `role` HTTP header (or Python kwarg) ∈ `{doctor, nurse, admin}` — **not cryptographically verified** | `ingestion/metadata/rbac_policy.py::get_ingest_allowed_roles()` |
| Retrieval result visibility | `role ∈ chunk.metadata.allowed_roles` or `role == "admin"` | `security/access_control.py::filter_results_by_role()` |
| Per-role PII visibility | role → masked-entity-types table | `ingestion/pii/role_based_masking.py::apply_role_mask()` |
| LLM input | 13 regex patterns for prompt-injection/jailbreak/system-prompt-extraction | `security/guardrails.py::check_input()` |
| LLM output | residual-PII detection and redaction | `security/guardrails.py::sanitise_output()` |

**Department → allowed roles** (`ingestion/metadata/rbac_policy.py`):

| Department | Allowed Roles |
|---|---|
| `general` | doctor, nurse, admin, researcher |
| `cardiology` | doctor, nurse, cardiologist, researcher |
| `billing` | billing, admin |
| `radiology` | doctor, nurse, radiologist, admin |
| `oncology` | doctor, nurse, admin |

**Per-role PII masking** (`ingestion/pii/role_based_masking.py`):

| Role | Masked Entities |
|---|---|
| `researcher` | PATIENT_NAME, MRN, DATE, PHONE_NUMBER, EMAIL_ADDRESS, SSN, PATIENT_DEMOGRAPHICS |
| `admin`, `billing` | all clinical entities (ICD10, LAB_VALUE, VITAL_SIGN, MEDICATION, DOSAGE_FREQ, DRUG_DOSE) |
| `doctor`, `nurse`, `cardiologist` | none — see full record |
| unrecognized role | everything masked (fail-safe default) |

## Business Rules

| BR-NN | Rule | Enforced In | Severity |
|---|---|---|---|
| BR-01 | `login()` checks a SHA-256 hash against a hardcoded 5-user table — no real user store, no password reset, no lockout | `security/auth.py` | CRITICAL (prototype-grade) |
| BR-02 | `admin` never fully bypasses masking | `ingestion/pii/role_based_masking.py` | CRITICAL |
| BR-03 | `check_input()` blocks 13 known prompt-injection patterns before a query reaches the LLM | `security/guardrails.py` | HIGH |
| BR-04 | `sanitise_output()` re-scans LLM output for residual PII before display | `security/guardrails.py` | HIGH |
| BR-05 | Encryption falls back to plaintext passthrough with a `logger.warning()` if unavailable — this is a silent degrade, not a hard failure | `security/encryption.py` | CRITICAL |
| BR-06 | Audit log write failures fall back to file-only logging with a warning, never block the calling operation | `security/audit_logger.py` | MEDIUM |

## External Integrations

None — this library has no external service calls; it's pure in-process logic plus a SQLite write for audit events (via [[Feat-0008-storage-persistence]]).

## Safe vs Dangerous Changes

### Safe
- Adding a new prompt-injection regex pattern to `check_input()`
- Adding a new masked entity type to an existing role's mask table

### Dangerous — Requires Review
| Change | Risk | Why |
|---|---|---|
| Adding a role without updating both the department map *and* the masking table | A role that can retrieve chunks but has no masking entry falls through to the "unrecognized role" fail-safe — likely not the intended behavior, but silent |
| Changing the SHA-256 hashing in `auth.py` without a migration path | The hardcoded `_USERS` table would need re-hashing; there is no user-management tooling |
| Loosening `filter_results_by_role()`'s admin/role check | Directly widens PHI exposure across the whole product | 

### Human Escalation Required
- Replacing the hardcoded `_USERS` table with a real identity provider — this is the single highest-leverage security change available in this codebase and touches every consumer of `security/auth.py`.
- Adding token/JWT verification to the FastAPI endpoints in [[Feat-0003-document-ingestion]] and [[Feat-0001-ade-extraction-service]] — currently there is none.

## Known Error Scenarios

| Scenario | Error Returned | Root Cause |
|---|---|---|
| Bad login credentials | `login()` returns `False`, no audit event | intentional — avoids logging credential attempts |
| Insufficient ingest role | `HTTPException 403` | [[Feat-0003-document-ingestion]] checking this library's role set |
| Unknown department | `ValueError` | `rbac_policy.get_allowed_roles()` |
| Encryption key unavailable | plaintext passthrough + warning log | `security/encryption.py` |
| Audit DB write fails | file-only fallback + warning log | `security/audit_logger.py` |

## Testing Expectations

- `tests/unit/test_researcher_role.py` is the primary coverage: masking correctness per role,
  RBAC filtering per department, and the combined `secure_results()` pipeline.
- No test coverage found for `security/auth.py` (login/logout/session flow) or
  `security/guardrails.py` (injection blocking, output sanitization) — both are open gaps.

## Key Files

- `security/auth.py` — Streamlit session login against a hardcoded user table
- `security/access_control.py` — `filter_results_by_role()`, the sole RBAC chunk-visibility gate
- `security/audit_logger.py` — `log_event()`/`get_audit_trail()`, writes to `audit_log` + file
- `security/encryption.py` — Fernet-based PHI field encryption, key from env or a local file
- `security/guardrails.py` — `check_input()`/`sanitise_output()` around the LLM call
- `ingestion/metadata/rbac_policy.py` — department→roles authority
- `ingestion/pii/role_based_masking.py` — role→masked-entity-types authority

## Context Routing

| Feature | Load when |
|---|---|
| Feat-0007-security-access-control | touching login, RBAC, PII masking, audit logging, encryption, or LLM input/output guardrails |

## Forbidden Patterns

- Never add a new role to the department map without adding a corresponding entry to the masking table — an omission here silently falls back to "mask everything," which may hide data a role should legitimately see.
- Never treat `admin` as a full bypass anywhere new — it is explicitly scoped to RBAC visibility only, not masking, everywhere else in this codebase.
- Never log a failed login attempt's password, even at DEBUG.

## Architectural Decisions

| Decision | Reason | Do Not Change Without |
|---|---|---|
| Role is self-asserted (HTTP header / Python kwarg), never cryptographically verified | Prototype-stage; the Streamlit UI is the only real gate and everything downstream trusts it | Recognizing this is the single biggest security gap in the repo — see `.claude/rules/security.md`'s Project Auth Model for the full writeup |
| Encryption failure degrades to plaintext rather than blocking ingestion | Availability over strict confidentiality for this prototype | This is a deliberate but risky tradeoff — flag it if the deployment target is ever real PHI |

## Known Gaps

- **No authentication at all on the FastAPI layer** — `role` is a plain unsigned header on `POST /ingest/bulk` (see [[Feat-0003-document-ingestion]]), and `/extract`/`/health` in [[Feat-0001-ade-extraction-service]] have no auth whatsoever.
- No test coverage for `auth.py` or `guardrails.py`.
- No password reset, account lockout, or rate limiting on login attempts.
- Encryption key rotation has no defined process; a key stored in a local file has no protection beyond filesystem permissions.
- `get_audit_trail()` (used by [[Feat-0006-streamlit-ui]]'s audit page) has no role restriction of its own — any authenticated user can view the full audit trail, not just admins.
