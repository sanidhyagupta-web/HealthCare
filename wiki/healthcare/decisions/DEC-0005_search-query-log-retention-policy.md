---
title: "Search query log retention policy"
date: 2026-08-21
id: DEC-0005
feature: search-audit-logging
source_meeting: healthcare-semantic-search-sprint-planning-2026-08-21
recording_id: 1lipgt5Kvq5M_jXDkPT2h0QBZrAhqQmyMYWwpOotWWAs
transcript_id: 1lipgt5Kvq5M_jXDkPT2h0QBZrAhqQmyMYWwpOotWWAs
type: unresolved
evidence_quote: "We still need to figure out the retention policy for search query logs. I need a legal read on whether separating query text from access events satisfies our obligations, and Marcus needs a read from the clinical council on the chilling effect."
reconciliation:
  existed_before: false
  previously_rejected: false
  contradicts: []
  on_roadmap: false
  dependencies: []
  changes_plan: false
linear_issue: https://linear.app/flightdecktest-2/issue/ABC-9/dec-0005-search-query-log-retention-policy
---

## Statement
The retention policy for search query logs is unresolved: Security/Compliance wants every query retained 7 years with user identity attached (matching chart-access logging), Clinical Informatics is concerned this will suppress exploratory searches, and a middle option (7-year retention for access events, ~90-day retention for raw query text) was proposed but not adopted pending a legal read and clinical council input; the search endpoint will be built behind a flag and not enabled for real users until this is resolved.

## Reconciliation Notes
No prior decision on query log retention exists for this project; nothing to conflict with or supersede. This stays open per the meeting's own conclusion ("we are not deciding this today").
