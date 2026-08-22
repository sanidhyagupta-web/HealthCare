---
title: "PII Redaction Pipeline"
slug: pii-redaction
owners:
  - Sanidhya Gupta
status: active
last_updated: 2026-08-21
proposed_by: agent
identity_confirmed: false
---

## Current State
Ingestion workers currently embed raw clinical text with no redaction step — patient names, medical record numbers, and dates of birth are entering the vector store as embeddings. A deterministic PII redaction stage has been decided ([DEC-0001](../../decisions/DEC-0001_pii-redaction-before-embedding.md)) to run before the embedding step, but is not yet implemented.

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
| 2026-08-21 | [Deterministic PII redaction before embedding](../../decisions/DEC-0001_pii-redaction-before-embedding.md) | decided | _draft, not yet filed_ |

## Evidence
- [DEC-0001](../../decisions/DEC-0001_pii-redaction-before-embedding.md)

## Open Questions
- Is `pii-redaction` the right feature request for this work, or does it belong to an existing one? Created by an agent from decision DEC-0001 (meeting: healthcare-semantic-search-sprint-planning-2026-08-21); rename or merge if wrong.

**Resolved:**
- Nothing recorded yet.

## Risks / Rejected Approaches
- An LLM-based redaction pass was considered and rejected: not deterministically reproducible for audit purposes, and too slow at ~40,000 documents/night ([DEC-0001](../../decisions/DEC-0001_pii-redaction-before-embedding.md)).

## Relationships
**Depends On:** Nothing recorded yet.
**Related:** [hybrid-search](../hybrid-search/feature-request.md) — redacted/tokenized text is what gets embedded and indexed for search.
