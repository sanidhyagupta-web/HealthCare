# Implementation Plan — [Feature Name]

> Copy to `features/active/<feature-name>/03-implementation-plan.md`.
> Fill after 02-technical-spec.md is complete.
> Work through steps in order. Check off each step when done.

## Pre-work
- [ ] Read relevant skill files (listed in technical spec).
- [ ] Confirm `app/config.py` has any new settings keys needed.
- [ ] Confirm DB migration is planned if models change.

## Step 1 — DB / Config changes
_Always first. Downstream code depends on models and settings._

- [ ] Add new columns/tables to `db/models.py`.
- [ ] Add migration SQL to `db/migrations/`.
- [ ] Add new config keys to `app/config.py` + `.env.example`.

## Step 2 — Core logic (ingestion or retrieval)

_For ingestion features:_
- [ ] Implement the new parser / chunker / worker in the appropriate `ingestion/` or `workers/` subdirectory.
- [ ] Extend `ingestion/state_machine.py` if new statuses are needed.
- [ ] Register documents with `ingestion/registry.py`.

_For search features:_
- [ ] Implement retrieval change in `indexing/`.
- [ ] Update RRF merge or reranker if retrieval candidates change.
- [ ] Ensure `filter_results_by_role` is called before the LLM.

## Step 3 — Security & Compliance
- [ ] PII detection runs on any new text path (`ingestion/pii/pii_detector.py`).
- [ ] Redacted text only, never raw, goes to Chroma or BM25 index.
- [ ] `allowed_roles` written to chunk metadata via `rbac_policy.py`.
- [ ] Role masking applied in `ingestion/pii/role_based_masking.py` if new role introduced.
- [ ] Audit log events added to `security/audit_logger.py`.

## Step 4 — Queue wiring
- [ ] New worker added to `queues/__init__.py` if needed.
- [ ] Worker started in `run.py`.
- [ ] Input and output queue names documented in worker docstring.

## Step 5 — Tests
- [ ] Unit test for new core logic (parser, chunker, retrieval function).
- [ ] Integration test: seed one document, run pipeline end-to-end, assert status = `INDEXED`.
- [ ] RBAC test: assert role X cannot access document from department Y.
- [ ] Audit test: assert correct event appears in `logs/audit.log` after action.

## Step 6 — Eval
- [ ] If retrieval behavior changed: run `evaluation/run_eval.py` and record Hit@5 / MRR@5.
- [ ] If ingestion changed: add a test document to `scripts/` and verify it reaches `INDEXED`.
- [ ] Add or update eval case in `evals/` if this is a repeatable pattern.

## Step 7 — Documentation
- [ ] Update relevant skill file if a new pattern was introduced.
- [ ] Add feature to `features/active/<feature-name>/notes.md` with run instructions.
- [ ] Feature runnable from fresh checkout: document the exact command.

## Rollback plan
_How to undo this if it breaks prod._

_Example: revert the worker registration in `run.py`; the queue will simply not be consumed and documents will not fail — they will remain in `CHUNKED` status._
