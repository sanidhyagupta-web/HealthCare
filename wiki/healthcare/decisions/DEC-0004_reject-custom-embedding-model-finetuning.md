---
title: "Reject custom clinical embedding model fine-tuning this quarter"
date: 2026-08-21
id: DEC-0004
feature: hybrid-search
source_meeting: healthcare-semantic-search-sprint-planning-2026-08-21
recording_id: 1lipgt5Kvq5M_jXDkPT2h0QBZrAhqQmyMYWwpOotWWAs
transcript_id: 1lipgt5Kvq5M_jXDkPT2h0QBZrAhqQmyMYWwpOotWWAs
type: rejected
evidence_quote: "Then we're not going to fine tune a custom embedding model this quarter. We're ruling it out. We stay on the off the shelf model and we invest that time in better chunking instead, semantic boundaries rather than fixed token windows."
reconciliation:
  existed_before: false
  previously_rejected: false
  contradicts: []
  on_roadmap: false
  dependencies: []
  changes_plan: false
linear_issue: https://linear.app/flightdecktest-2/issue/ABC-8/dec-0004-reject-custom-clinical-embedding-model-fine-tuning-this
---

## Statement
The team rejected fine-tuning a custom clinical embedding model on the internal corpus this quarter — citing the lack of a labelled clinical relevance dataset, the compliance burden of a model trained on patient data becoming itself regulated, and evidence that current retrieval failures are lexical/chunking issues rather than embedding-quality issues — and will instead stay on the off-the-shelf embedding model and invest in semantic-boundary chunking.

## Reconciliation Notes
Maps to the same feature as [DEC-0002](DEC-0002_hybrid-retrieval-search-endpoint.md) (hybrid-search) since it concerns the embedding model backing that same retrieval capability; it doesn't contradict or change DEC-0002, which didn't specify an embedding-model strategy.
