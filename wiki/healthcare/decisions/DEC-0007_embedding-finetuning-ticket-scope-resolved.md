---
title: "Embedding fine-tuning rejection ticket: scope, AC, and success metrics finalized"
date: 2026-08-22
id: DEC-0007
feature: hybrid-search
source_meeting: "Linear ticket ABC-8"
recording_id: ABC-8
transcript_id: https://linear.app/flightdecktest-2/issue/ABC-8/dec-0004-reject-custom-clinical-embedding-model-fine-tuning-this
type: superseded
evidence_quote: "This ticket is a decision-record-only ticket: record and communicate the fine-tuning rejection plus the follow-on direction. Create a separate, linked implementation ticket for the entity-preserving chunker improvements, with the success criteria above."
reconciliation:
  existed_before: true
  previously_rejected: false
  contradicts: []
  on_roadmap: false
  dependencies: [DEC-0004]
  changes_plan: true
supersedes: [DEC-0006]
linear_issue: https://linear.app/flightdecktest-2/issue/ABC-8/dec-0004-reject-custom-clinical-embedding-model-fine-tuning-this
---

## Statement
Ticket ABC-8's round-1 open questions were fully answered in round 2: acceptance criteria were trimmed to cover only the fine-tuning rejection and its chunking follow-on (the duplicated hybrid-search AC was removed), the chunking investment was confirmed to target improving the production `entity_preserving_chunker.py` rather than switching to the unused `semantic_chunker.py`, success was defined as reducing mid-sentence chunk splits from ~11% to ≤2% with zero splits inside protected medical entity groups, a revisit trigger for the fine-tuning rejection was defined (a labelled clinical relevance dataset becomes available AND the chunking work is evaluated against its success criteria and found insufficient), and the ticket's scope was confirmed as decision-record-only, with chunking implementation split to a future, separately-filed ticket.

## Reconciliation Notes
Supersedes [DEC-0006](DEC-0006_embedding-finetuning-ticket-scope-ambiguity.md), whose five open questions this round's answers close out; it does not change or contradict [DEC-0004](DEC-0004_reject-custom-embedding-model-finetuning.md)'s underlying rejection of custom fine-tuning, only clarifies the scope, acceptance criteria, and success metrics around it.
