# wiki-resolution-handler

Runs only when `wiki-conflict-detector.md` sets `needs_resolution: true` — a genuine, unresolved
contradiction between this item and existing decision history that isn't a clean supersession.

## Input

An item carrying `reconciliation.contradicts` (one or more `DEC-NNNN` ids) and
`needs_resolution: true`.

## Steps

1. Read each contradicting `DEC-NNNN` in full — its `## Statement`, `evidence_quote`, and date.
2. Use `AskUserQuestion` to present the conflict, one at a time, never batched: this new item's
   `summary`/`evidence_quote` alongside the contradicting decision's `## Statement`. Ask how to
   resolve it:
   - **This new item supersedes the old one** — return `reconciled_type: "superseded"` and
     `supersedes: [<old DEC-NNNN>]`, so `wiki-writer.md` adds `superseded_by` to the old record and
     writes the new one with `supersedes` set.
   - **The old decision still stands; this new item is mistaken/outdated** — return
     `reconciled_type: "rejected"` for the new item (it's being explicitly turned down in favor of
     the standing decision) with a note referencing the old `DEC-NNNN`.
   - **Both are true in different contexts (false conflict)** — return the original
     `reconciled_type` unchanged, with a `## Reconciliation Notes` explanation for
     `wiki-writer.md` to record (e.g. "applies to a different environment/scope than DEC-0003").
   - **Genuinely unresolved — need more input before deciding** — return
     `reconciled_type: "unresolved"` regardless of what it was classified as before, with the
     contradiction noted; this stays open rather than forcing a resolution the user isn't ready
     to make.

## Output

`{ ...item, reconciled_type: <possibly changed>, resolution_notes: string }`

## Rules

- **Always ask, one conflict at a time** — never resolve a contradiction automatically, and never
  bundle multiple conflicting items into a single prompt (an answer to one can change the correct
  answer to the next, e.g. once the user says "the old one still stands," a second new item making
  the same claim should probably get the same treatment without re-asking from scratch — but
  confirm rather than assume, unless the two items are truly identical in substance).
- The resolution outcome flows straight into `wiki-writer.md` — this step doesn't write any wiki
  files itself, only decides `reconciled_type` and captures the reasoning as
  `resolution_notes` for the eventual `## Reconciliation Notes` section.
- **`resolution_notes` ends up in a Linear ticket, so write it for the person holding that ticket.**
  `wiki-writer.md` folds it into `## Reconciliation Notes`, which is read verbatim into the ticket's
  `## Existing System Behavior` — see that skill's "Product language, not technical language". So:
  describe the two behaviours that disagree and what a human has to choose between, in product terms.
  Do not narrate this step's own process — not which branch was taken, not that a rule required
  leaving it `unresolved`, not the `reconciliation` frontmatter restated as prose. The
  `reconciled_type` already records the outcome; these notes exist to tell a human what the conflict
  actually is. And never quote the transcript here: the verbatim line lives in `evidence_quote`,
  which is deliberately kept out of the ticket.
