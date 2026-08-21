---
feat_id: Feat-0005
feature: semantic-search-qa
type: backend-service
domain: retrieval-qa
criticality: high
touched_paths:
  - search/pipeline.py
  - llm/claude_client.py
depends_on: [Feat-0002-document-indexing, Feat-0007-security-access-control]
consumed_by: [Feat-0006-streamlit-ui]
implements: []
tags: [rag, search, llm, rbac]
---

## Overview

| | |
|---|---|
| Type | backend-service |
| Package | `search/` + `llm/claude_client.py` (of `llm/`'s 4 files — see [[Feat-0001-ade-extraction-service]] for the other two) |
| Path | `search/pipeline.py`, `llm/claude_client.py` |
| Domain | Query-time read path: secure the retrieved chunks, then generate a cited natural-language answer |
| Last updated | initial scan |

## Domain Purpose

Takes chunks already retrieved by [[Feat-0002-document-indexing]] and makes them safe and useful
to return to a specific user: RBAC-filters by role, masks PII per role, then asks Claude to
synthesize a cited answer grounded only in what that user is allowed to see.

## Entities Owned

None — this is a read-only, stateless pipeline over chunk dicts (see
[[Schemas/schemas.md#implicit-schema--vectorkeyword-index-chunk-metadata]]).

## Invariants

- **Call order is non-negotiable**: RBAC filtering must run before role masking, which must run
  before the chunk text reaches the LLM (`search/pipeline.py` docstring makes this explicit).
- Role masking applies to *every* role, including `admin` — there is no masking bypass.
- `generate_answer()` never raises on API failure — a missing key, an empty context, or an
  Anthropic API exception all return a `(message, [])` tuple instead of propagating an exception.
- Cited excerpt indices returned by the LLM are validated as 1-based and within
  `len(context_chunks)` before being trusted.

## Access Control

**Model**: delegated. This feature calls [[Feat-0007-security-access-control]]'s
`filter_results_by_role()` and `ingestion/pii/role_based_masking.py`'s `apply_role_mask()` — it
does not implement RBAC itself, it *orders* the two calls correctly.

| Action | Access Condition | Enforced In |
|---|---|---|
| `secure_results(results, user_role)` | role ∈ chunk's `allowed_roles`, or role == `admin` | delegates to [[Feat-0007-security-access-control]] |
| PII visibility per role | role-specific entity mask table | delegates to `ingestion/pii/role_based_masking.py` |

## Business Rules

| BR-NN | Rule | Enforced In | Severity |
|---|---|---|---|
| BR-01 | RBAC filter must run before masking, never the reverse | `search/pipeline.py` | CRITICAL |
| BR-02 | Researcher role never sees `PATIENT_NAME`, `MRN`, `DATE`, `PHONE_NUMBER`, `EMAIL_ADDRESS`, `SSN`, `PATIENT_DEMOGRAPHICS` | `ingestion/pii/role_based_masking.py` | CRITICAL |
| BR-03 | Admin and billing roles have clinical content masked (ICD10, lab values, vitals, medications) even though they bypass the RBAC chunk-visibility filter | `ingestion/pii/role_based_masking.py` | HIGH |
| BR-04 | An unrecognized role masks *everything* — fail-safe, not fail-open | `ingestion/pii/role_based_masking.py` | CRITICAL |
| BR-05 | The LLM must cite every factual claim with an inline `[N]` reference and must not reconstruct redacted identifiers | system prompt in `llm/claude_client.py` — a prompt-level rule, not code-enforced | MEDIUM |
| BR-06 | Missing `ANTHROPIC_API_KEY` degrades to a user-facing config message, not a crash | `llm/claude_client.py` | MEDIUM |

## External Integrations

| System | Trigger | What Happens |
|---|---|---|
| Anthropic API (`anthropic` SDK, lazily imported) | every `generate_answer()` call with non-empty context | `messages.create()`; failures caught and returned as an in-band error message |

## Safe vs Dangerous Changes

### Safe
- Tuning the system prompt's tone/instructions in `llm/claude_client.py` as long as the citation contract (`[N]` markers, 1-based indices) is preserved

### Dangerous — Requires Review
| Change | Risk | Why |
|---|---|---|
| Reordering `filter_results_by_role()` and `apply_role_mask()` calls | Directly breaks the RBAC/masking security invariant this whole feature exists to enforce | 
| Changing the `context_chunks` shape this feature expects | No formal schema exists for it (see Gaps) — a silent mismatch would only surface as a wrong/garbled answer, not an error |

### Human Escalation Required
- Any change to how "unknown role → mask everything" behaves — this is the fail-safe backstop for a role the system doesn't recognize.

## Known Error Scenarios

| Scenario | Error Returned | Root Cause |
|---|---|---|
| Missing `ANTHROPIC_API_KEY` | `("Anthropic API key is not configured...", [])` | config check before the API call |
| Empty `context_chunks` | `("No relevant medical records were found for your query.", [])` | early return, no LLM call made |
| Anthropic API exception | `(f"LLM unavailable: {exc}", [])`, logged at ERROR | caught broadly around the API call |
| Chunk metadata missing `allowed_roles` | treated as empty list → blocks all non-admin access | [[Feat-0007-security-access-control]]'s `filter_results_by_role()` |

## Testing Expectations

- `tests/unit/test_researcher_role.py` covers `apply_role_mask()` and `filter_results_by_role()`
  extensively (researcher/doctor/nurse/billing scenarios) and `secure_results()` end-to-end.
- *Open question: no tests found for `generate_answer()` itself* — the Anthropic call path is
  untested (no mock of the `anthropic` client observed in `tests/unit/`).

## Key Files

- `search/pipeline.py` — `secure_results()`: the RBAC → masking orchestration, with the call-order invariant documented in its own module docstring
- `llm/claude_client.py` — `generate_answer()`: prompt construction, Anthropic call, citation parsing

## Context Routing

| Feature | Load when |
|---|---|
| Feat-0005-semantic-search-qa | touching the RBAC/masking call order, the answer-generation prompt, or citation handling |

## Forbidden Patterns

- Never call `apply_role_mask()` before `filter_results_by_role()` — the module docstring in `search/pipeline.py` states this ordering is non-negotiable, and reversing it would let a masked-but-still-visible chunk leak to a role that shouldn't see it filtered out at all.
- Never pass raw, unmasked chunk text to `generate_answer()` — it has no PII-safety logic of its own; it trusts the caller.

## Architectural Decisions

| Decision | Reason | Do Not Change Without |
|---|---|---|
| RBAC filtering happens in application code at query time, not as a database-level row-security policy | The retrieval backends (Chroma, BM25) have no native row-level security concept | Understanding that this makes `search/pipeline.py`'s call order the *entire* security boundary for query results — there is no defense in depth here |

## Known Gaps

- No formal schema/type for `context_chunks` passed into `generate_answer()` — inferred from usage only.
- No test coverage for the Claude API call path itself.
- Input guardrails (`security/guardrails.py::check_input`) and output guardrails (`sanitise_output`) are called by [[Feat-0006-streamlit-ui]] around this feature, not by this feature itself — this service assumes pre-validated input and does not sanitize its own output.
