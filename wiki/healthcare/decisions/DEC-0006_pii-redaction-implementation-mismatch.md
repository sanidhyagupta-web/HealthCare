---
title: "PII redaction implementation contradicts DEC-0001"
date: 2026-08-22
id: DEC-0006
feature: pii-redaction
source_meeting: "Linear ticket ABC-5"
recording_id: ABC-5
transcript_id: https://linear.app/flightdecktest-2/issue/ABC-5/dec-0001-deterministic-pii-redaction-before-embedding
type: superseded
evidence_quote: "A PII redaction stage already exists and is already wired into the ingestion pipeline (`workers/pii_worker.py`, running between `pii_queue` and `extraction_queue`, i.e. before `embedding_queue` — so it already runs before embedding, per the one requirement it does satisfy)."
reconciliation:
  existed_before: true
  previously_rejected: false
  contradicts: [DEC-0001]
  on_roadmap: true
  dependencies: [DEC-0001]
  changes_plan: true
supersedes: [DEC-0001]
linear_issue: https://linear.app/flightdecktest-2/issue/ABC-5/dec-0001-deterministic-pii-redaction-before-embedding
---

## Statement
DEC-0001's decided design (deterministic, model-free PII redaction producing stable per-patient pseudonymous tokens) is superseded: the codebase reality check on ticket ABC-5 found the deployed pipeline (`workers/pii_worker.py`, `ingestion/pii/pii_detector.py`, `ingestion/pii/pii_redactor.py`) uses Presidio (a model) as its primary detector and redacts to generic type-only placeholders rather than stable per-patient tokens, contradicting the two core requirements that made DEC-0001's design distinctive.

## Reconciliation Notes
Ticket ABC-5 was rejected by product-align-loop's round-1 codebase check as a mismatch against DEC-0001, not confirmed as-is, so this record supersedes DEC-0001 rather than duplicating it. A follow-up ticket scoped explicitly against the current implementation (replace Presidio with the deterministic-only path; add real per-patient stable tokenization) is recommended but not yet filed.
