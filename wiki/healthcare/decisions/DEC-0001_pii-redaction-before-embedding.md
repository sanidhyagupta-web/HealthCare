---
title: "Deterministic PII redaction before embedding"
date: 2026-08-21
id: DEC-0001
feature: pii-redaction
source_meeting: healthcare-semantic-search-sprint-planning-2026-08-21
recording_id: 1lipgt5Kvq5M_jXDkPT2h0QBZrAhqQmyMYWwpOotWWAs
transcript_id: 1lipgt5Kvq5M_jXDkPT2h0QBZrAhqQmyMYWwpOotWWAs
type: decided
evidence_quote: "We're going with a deterministic PII redaction stage in the ingestion pipeline that runs before the embedding step. Rule-based pattern matching plus a clinical entity dictionary, no model in the path."
reconciliation:
  existed_before: false
  previously_rejected: false
  contradicts: []
  on_roadmap: false
  dependencies: []
  changes_plan: false
linear_issue: https://linear.app/flightdecktest-2/issue/ABC-5/dec-0001-deterministic-pii-redaction-before-embedding
---

## Statement
The team will add a deterministic, rule-based PII redaction stage (pattern matching plus a clinical entity dictionary, no LLM) to the ingestion pipeline, running before embedding, that redacts patient names/MRNs/DOBs/addresses into stable pseudonymous tokens, writes an audit record per redaction, and fails closed to a dead-letter queue on error.

## Reconciliation Notes
This is the first decision recorded for this project — no prior decision history exists to conflict with, duplicate, or supersede.
