---
feat_id: Feat-0005
feature: search
type: backend-service
domain: rag-query-pipeline
criticality: high
touched_paths:
  - search/pipeline.py
depends_on: [security, ingestion]
consumed_by: []
implements: []
tags: [rag, rbac, pii-masking]
---

## Overview

| Type | Package | Path | Domain | Last updated |
|---|---|---|---|---|
| backend-service | `search` | `search/` | Post-retrieval security orchestration for RAG | 2026-09-17 (initial scan) |

## Domain Purpose

Defines the one function, `secure_results()`, that is supposed to be the mandatory
filter-then-mask gate between retrieval and the LLM in the query pipeline.

## Invariants

- The documented, non-negotiable call order (`AiHarness/skills/access-control.md:43-51`):
  `reranked_results → filter_results_by_role → apply_role_mask → generate_answer → log_event`.
- `secure_results()` itself implements this order correctly and must never mutate the input chunk
  dicts in place.

## Access Control

**Model**: role-based, delegated — this module orchestrates but does not itself decide access; see
[[security]] (`filter_results_by_role`) and [[ingestion]] (`apply_role_mask`,
`role_based_masking.py`).

| Action | Access Condition | Enforced In |
|---|---|---|
| chunk visibility | role ∈ chunk `allowed_roles` (or `admin`) | [[security]]`.access_control.filter_results_by_role`, called from here |
| PII masking of visible chunks | role-specific entity mask applied after the RBAC filter | [[ingestion]]`.pii.role_based_masking.apply_role_mask`, called from here |

## Business Rules

| BR-NN | Rule | Enforced In | Severity |
|---|---|---|---|
| BR-01 | RBAC filter must run before PII masking, which must run before the LLM sees any chunk | `search/pipeline.py` (correct here) | CRITICAL |

## Known Error Scenarios

*None found* — `secure_results()` has no explicit error branches; it is a straight pipeline of two
function calls.

## Architectural Decisions

| Decision | Reason | Do Not Change Without |
|---|---|---|
| `secure_results()` exists as a single call site for the filter→mask order | Prevent every caller from having to remember and re-implement the ordering | See the CRITICAL gap below — this decision is currently undermined by not being adopted everywhere |

## Safe vs Dangerous Changes

### Human Escalation Required
- **This entire feature's real-world effectiveness is currently a live security gap. Read this before touching the query path:**

  `search/pipeline.secure_results()` is **not called anywhere in the live application** — its only
  caller in the whole repo is `tests/unit/test_researcher_role.py`. The actual query path,
  `ui/search_page.py` (lines 45 and 63), calls `filter_results_by_role()` directly and then, per two
  independent scans (this feature's own scan and the repo-wide dependency map), passes results
  straight to `llm/claude_client.generate_answer()` at `ui/search_page.py:183` **without** calling
  `apply_role_mask()` first. This means the RBAC filter runs, but the PII-masking step that is
  supposed to run before every LLM call is skipped on the path real users hit — the LLM (and
  therefore anyone whose role can reach any matching chunk) may see PII tokens like
  `[PATIENT_NAME]`/`[MRN]` that the documented policy in `AiHarness/skills/access-control.md`
  requires to be masked for non-clinical roles (researcher, admin, billing).
- Any fix to this needs a design decision (route `ui/search_page.py` through `secure_results()`, or
  inline the missing `apply_role_mask()` call) — do not silently patch one call site without
  checking `evaluation/run_eval.py`, which the same scans report has the identical gap.

## Forbidden Patterns

- Never call `filter_results_by_role()` without immediately following it with `apply_role_mask()`
  before any chunk reaches an LLM — see the escalation note above for why this is not currently true
  everywhere.

## Key Files

- `search/pipeline.py` — `secure_results()`, the (currently under-adopted) filter→mask wrapper

## Context Routing

| Feature | Load when |
|---|---|
| Feat-0005-search | touching the query pipeline's security ordering, or investigating a PII-in-LLM-output report |

| Workflow | Sections to load |
|---|---|
| Any change to `ui/search_page.py`'s search flow | Safe vs Dangerous Changes (read the escalation note first) |
