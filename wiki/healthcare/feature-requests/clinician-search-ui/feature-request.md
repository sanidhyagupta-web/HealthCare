---
title: "Clinician Search Results Interface"
slug: clinician-search-ui
owners:
  - Marcus Feld
status: active
last_updated: 2026-08-21
proposed_by: agent
identity_confirmed: false
---

## Current State
No clinician-facing UI exists yet. A results page has been decided: each result renders as a card with the matched passage, and every card has a citation chip showing the source document title and page ([DEC-0003](../../decisions/DEC-0003_clinician-search-results-interface.md)).

## Key Facts
- Clinicians will not act on an answer they cannot verify, and will abandon a tool that shows an unsourced paragraph — observed behavior with two prior systems ([DEC-0003](../../decisions/DEC-0003_clinician-search-results-interface.md)).

## Requirements
- Each result renders as a card containing the matched passage.
- Every card has a clickable citation chip showing the source document title and page, which opens the original document scrolled to that page with the passage highlighted ([DEC-0003](../../decisions/DEC-0003_clinician-search-results-interface.md)).
- The matched passage must be visually highlighted inside the card itself, not only on the opened page ([DEC-0003](../../decisions/DEC-0003_clinician-search-results-interface.md)).
- An empty result set must be shown as an explicit empty state — never a blank page and never a fabricated summary ([DEC-0003](../../decisions/DEC-0003_clinician-search-results-interface.md)).

## Business Rules
- Nothing recorded yet.

## Decisions
| Date | Title | Type | Ticket |
|---|---|---|---|
| 2026-08-21 | [Clinician search results interface with page-level citations](../../decisions/DEC-0003_clinician-search-results-interface.md) | decided | _draft, not yet filed_ |

## Evidence
- [DEC-0003](../../decisions/DEC-0003_clinician-search-results-interface.md)

## Open Questions
- Is `clinician-search-ui` the right feature request for this work, or does it belong to an existing one? Created by an agent from decision DEC-0003 (meeting: healthcare-semantic-search-sprint-planning-2026-08-21); rename or merge if wrong.

**Resolved:**
- Nothing recorded yet.

## Risks / Rejected Approaches
- Nothing recorded yet.

## Relationships
**Depends On:** [hybrid-search](../hybrid-search/feature-request.md) — renders results returned by the hybrid search endpoint; page number and source document id used for citations come from ingestion metadata carried through that endpoint.
