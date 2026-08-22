---
title: "Open scope and AC ambiguity on the embedding fine-tuning rejection ticket"
date: 2026-08-22
id: DEC-0006
feature: hybrid-search
source_meeting: "Linear ticket ABC-8"
recording_id: ABC-8
transcript_id: https://linear.app/flightdecktest-2/issue/ABC-8/dec-0004-reject-custom-clinical-embedding-model-fine-tuning-this
type: unresolved
evidence_quote: "Is this ticket meant to be a decision record only (no code changes), or does it also carry the chunking-investment implementation work itself? Scope boundaries are currently unspecified."
reconciliation:
  existed_before: false
  previously_rejected: false
  contradicts: []
  on_roadmap: false
  dependencies: [DEC-0004]
  changes_plan: false
linear_issue: https://linear.app/flightdecktest-2/issue/ABC-8/dec-0004-reject-custom-clinical-embedding-model-fine-tuning-this
---

## Statement
Ticket ABC-8, which tracks DEC-0004's rejection of custom embedding-model fine-tuning, has five open questions after round 1 of the align loop: whether its acceptance criteria (a verbatim copy of the separate hybrid-search ticket's AC) belong on this ticket at all, which chunker module ("entity_preserving_chunker.py" vs. the unused "semantic_chunker.py") the semantic-boundary chunking investment is meant to target, whether a trigger exists for revisiting the fine-tuning rejection later, what success metric governs the chunking investment, and whether this ticket's scope is a decision record only or also carries the chunking implementation work itself.

## Reconciliation Notes
DEC-0004 already records the underlying rejection decision and is not contradicted or changed by this item — the codebase reality check in round 1 confirmed the off-the-shelf embedding model and existing entity-aware chunker are consistent with DEC-0004. This item instead captures ABC-8's own unresolved scope/AC ambiguity as a distinct ledger entry, dependent on DEC-0004.
