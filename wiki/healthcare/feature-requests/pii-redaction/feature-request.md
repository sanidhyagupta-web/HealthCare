---
title: "PII Redaction Pipeline"
slug: pii-redaction
owners:
  - Sanidhya Gupta
status: active
last_updated: 2026-08-22
proposed_by: agent
identity_confirmed: false
---

## Current State
Ingestion workers already run a PII redaction stage (`workers/pii_worker.py`) before embedding, but it does not match the deterministic design decided in DEC-0001: it uses Presidio (a model) as its primary detector, falling back to regex/dictionary matching only when Presidio isn't installed, and redacts to generic type-only placeholders (e.g. `[PATIENT_NAME]`, `[MRN]`) rather than stable per-patient pseudonymous tokens. DEC-0001 is superseded by [DEC-0006](../../decisions/DEC-0006_pii-redaction-implementation-mismatch.md) pending a follow-up ticket scoped against the real implementation.

## Key Facts
- Ingestion volume is roughly 40,000 documents/night, which ruled out an LLM-based redaction pass on latency grounds ([DEC-0001](../../decisions/DEC-0001_pii-redaction-before-embedding.md)).

## Requirements
- Redact patient names, medical record numbers, dates of birth, and full addresses using deterministic rule-based pattern matching plus a clinical entity dictionary — no model in the path ([DEC-0001](../../decisions/DEC-0001_pii-redaction-before-embedding.md)).
- Replace each redacted value with a stable pseudonymous token so the same patient maps to the same token across documents, preserving searchability ([DEC-0001](../../decisions/DEC-0001_pii-redaction-before-embedding.md)).
- Write an audit record for every redaction performed, including document id, field type, and timestamp ([DEC-0001](../../decisions/DEC-0001_pii-redaction-before-embedding.md)).
- Fail closed: if the redaction stage errors on a chunk, that chunk must not be embedded — route it to a dead letter queue for human review instead ([DEC-0001](../../decisions/DEC-0001_pii-redaction-before-embedding.md)).

## Business Rules
- Redaction must happen before embedding, never after ([DEC-0001](../../decisions/DEC-0001_pii-redaction-before-embedding.md)).

## Decisions
| Date | Title | Type | Ticket |
|---|---|---|---|
| 2026-08-21 | [Deterministic PII redaction before embedding](../../decisions/DEC-0001_pii-redaction-before-embedding.md) | decided | [Linear](https://linear.app/flightdecktest-2/issue/ABC-5/dec-0001-deterministic-pii-redaction-before-embedding) |
| 2026-08-22 | [PII redaction implementation contradicts DEC-0001](../../decisions/DEC-0006_pii-redaction-implementation-mismatch.md) | superseded | [Linear](https://linear.app/flightdecktest-2/issue/ABC-5/dec-0001-deterministic-pii-redaction-before-embedding) |

## Evidence
- [DEC-0001](../../decisions/DEC-0001_pii-redaction-before-embedding.md)
- [DEC-0006](../../decisions/DEC-0006_pii-redaction-implementation-mismatch.md)

## Open Questions
- Is `pii-redaction` the right feature request for this work, or does it belong to an existing one? Created by an agent from decision DEC-0001 (meeting: healthcare-semantic-search-sprint-planning-2026-08-21); rename or merge if wrong.
- Should a follow-up ticket be filed scoped against the current implementation (replace Presidio with the deterministic-only path; add real per-patient stable tokenization), or should DEC-0001's design be reconsidered instead ([DEC-0006](../../decisions/DEC-0006_pii-redaction-implementation-mismatch.md))?

**Resolved:**
- Nothing recorded yet.

## Risks / Rejected Approaches
- An LLM-based redaction pass was considered and rejected: not deterministically reproducible for audit purposes, and too slow at ~40,000 documents/night ([DEC-0001](../../decisions/DEC-0001_pii-redaction-before-embedding.md)).
- The current deployed redaction stage uses Presidio (a model) as its primary detector and collapses every value of a given type to the same generic placeholder — this contradicts DEC-0001 and needs replacing, not extending ([DEC-0006](../../decisions/DEC-0006_pii-redaction-implementation-mismatch.md)).

## Relationships
**Depends On:** Nothing recorded yet.
**Related:** [hybrid-search](../hybrid-search/feature-request.md) — redacted/tokenized text is what gets embedded and indexed for search.
