---
title: "Hybrid retrieval search endpoint (BM25 + vector + RRF)"
date: 2026-08-21
id: DEC-0002
feature: hybrid-search
source_meeting: healthcare-semantic-search-sprint-planning-2026-08-21
recording_id: 1lipgt5Kvq5M_jXDkPT2h0QBZrAhqQmyMYWwpOotWWAs
transcript_id: 1lipgt5Kvq5M_jXDkPT2h0QBZrAhqQmyMYWwpOotWWAs
type: decided
evidence_quote: "Then we're going with hybrid retrieval using BM25 plus vector search combined by reciprocal rank fusion."
reconciliation:
  existed_before: false
  previously_rejected: false
  contradicts: []
  on_roadmap: false
  dependencies: []
  changes_plan: false
linear_issue: https://linear.app/flightdecktest-2/issue/ABC-6/dec-0002-hybrid-retrieval-search-endpoint-bm25-vector-rrf
superseded_by: DEC-0006
---

## Statement
The team will build a single search endpoint that runs a BM25 keyword query and a vector similarity query in parallel and fuses the two ranked lists with reciprocal rank fusion, exposed as one endpoint (query string, optional document-type/date-range filter, result limit defaulting to 20, returning chunk text/source document id/page number/fusion score, p95 latency under 800ms, with the caller's access scope enforced inside the query itself).

## Reconciliation Notes
No prior decision on retrieval strategy exists for this project; this does not conflict with or duplicate anything already recorded.
