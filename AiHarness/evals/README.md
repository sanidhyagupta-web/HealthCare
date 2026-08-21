# Evals — How to Run and What Passing Looks Like

## Purpose
Evals verify that the AI harness actually works. Each eval case is a feature request you'd give a coding tool. Run it fresh — no hand-holding — and compare output to `expected.md`.

If you can't get 3 of the 5 cases to pass, the harness needs sharpening. Fix the relevant skill file, re-run, iterate.

## How to run an eval

1. Open a **fresh chat** in Cursor or Claude Code. Do not use an existing thread.
2. Point the tool at `AiHarness/Agents.md`: `"Load AiHarness/Agents.md as your project context."`
3. Paste the prompt from the case's `prompt.md` verbatim.
4. Let it run **end-to-end without interventions**. Do not answer clarifying questions — if it asks many, that's a harness failure.
5. Compare the output to `expected.md`.
6. Write findings in `result-notes.md`.
7. If the eval fails, identify which skill file is missing or unclear and update it.

## What "passing" means

- The agent created `features/active/<feature-name>/` and filled all three templates.
- It used skills from `skills/` — no invented conventions.
- It followed the implementation plan step order (DB → logic → security → queue → tests).
- It did not violate any non-negotiable rules (no hardcoded creds, no fake test data, no skipped PII masking, no unredacted chunks on disk).
- Generated code matches the style of existing workers, chunkers, and registry calls.
- Minimal or zero back-and-forth was needed.

## Eval cases

| # | Case | What it stresses | Status |
|---|---|---|---|
| 01 | DICOM image loader | Document ingestion + chunking | PASS |
| 02 | Audit-logged search endpoint | Hybrid search + audit + access control | Not run |
| 03 | Researcher role with PII redaction | PII masking + access control | PASS |
| 04 | Handwritten prescription re-OCR | OCR fallback path + entity-preserving chunker | Not run |
| 05 | Embedding model swap | Embedding generation + eval pipeline guard | Not run |
| 06 | DLQ retry and failure handling | BaseWorker retry pattern + failure observability | Not run |
| 07 | Duplicate document detection | File-level + chunk-level SHA-256 dedup | Not run |
| 08 | Audit log query endpoint | Audit logging + RBAC on audit trail itself | Not run |
| 09 | Bulk document ingestion | Ingestion entry point + batch error isolation | Not run |
| 10 | Patient-scoped search | pii_entity_index + RBAC on scoped queries | Not run |

## Skill coverage matrix

| Skill | Cases that stress it |
|---|---|
| `document-ingestion.md` | 01, 04, 06, 09 |
| `chunking-strategy.md` | 01, 04, 07 |
| `pii-masking.md` | 03, 10 |
| `access-control.md` | 02, 03, 06, 08, 09, 10 |
| `embedding-generation.md` | 05 |
| `hybrid-search.md` | 02, 10 |
| `audit-logging.md` | 02, 06, 07, 08, 09, 10 |
| `llm-response-validation.md` | 02 |

## Scoring

For each case mark each criterion ✓ / ✗ / partial:

| Criterion | Weight |
|---|---|
| Templates created and filled | 20% |
| Correct skills referenced | 20% |
| Implementation plan followed in order | 20% |
| Non-negotiables respected | 20% |
| Code style matches existing repo | 20% |

A case passes at ≥ 80%. The harness is ready when ≥ 6 of 10 cases pass.
