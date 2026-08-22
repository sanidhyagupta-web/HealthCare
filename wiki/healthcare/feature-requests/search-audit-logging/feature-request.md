---
title: "Search Query Audit Logging & Retention"
slug: search-audit-logging
owners:
  - Dana Okoye
status: active
last_updated: 2026-08-21
proposed_by: agent
identity_confirmed: false
---

## Current State
Every clinician search needs to be logged for audit (who searched, what they searched, what came back), but the retention policy for that log is unresolved ([DEC-0005](../../decisions/DEC-0005_search-query-log-retention-policy.md)). Until it's closed, the search endpoint is being built behind a feature flag and will not be enabled for real users.

## Key Facts
- A middle option was floated in the meeting but not agreed: retain access events (which documents were returned/opened) for 7 years, but retain raw query text for a much shorter period, e.g. 90 days ([DEC-0005](../../decisions/DEC-0005_search-query-log-retention-policy.md)).
- Concern raised: retaining raw query text under a clinician's name for 7 years could discourage exploratory differential-diagnosis searches, which are considered the most valuable kind ([DEC-0005](../../decisions/DEC-0005_search-query-log-retention-policy.md)).

## Requirements
- Nothing recorded yet — blocked on the open question below.

## Business Rules
- The search endpoint must not be enabled for real users until this retention policy is closed ([DEC-0005](../../decisions/DEC-0005_search-query-log-retention-policy.md)).

## Decisions
| Date | Title | Type | Ticket |
|---|---|---|---|
| 2026-08-21 | [Search query log retention policy](../../decisions/DEC-0005_search-query-log-retention-policy.md) | unresolved | _draft, not yet filed_ |

## Evidence
- [DEC-0005](../../decisions/DEC-0005_search-query-log-retention-policy.md)

## Open Questions
- What is the retention policy for search query logs? Needs a legal read on whether separating raw query text (short retention) from access events (7-year retention) satisfies audit obligations, and a read from the clinical council on the chilling effect of attaching clinician identity to retained queries. To be revisited next sprint ([DEC-0005](../../decisions/DEC-0005_search-query-log-retention-policy.md)).
- Is `search-audit-logging` the right feature request for this work, or does it belong to an existing one? Created by an agent from decision DEC-0005 (meeting: healthcare-semantic-search-sprint-planning-2026-08-21); rename or merge if wrong.

**Resolved:**
- Nothing recorded yet.

## Risks / Rejected Approaches
- Nothing recorded yet.

## Relationships
**Depends On:** Nothing recorded yet.
**Related:** [hybrid-search](../hybrid-search/feature-request.md) — the search endpoint is gated behind a flag pending resolution of this policy.
