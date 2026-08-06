# wiki-writer

Writes the actual wiki content — the one step in the pipeline that produces
`decisions/DEC-NNNN_<slug>.md` and edits `feature-requests/{id}/feature-request.md`. Follow
`wiki/SCHEMA.md` exactly for both file formats; this skill assumes that schema is already read.

## Input

A fully-reconciled item: `{ summary, evidence_quote, type, reconciled_type, feature, reconciliation, supersedes?, resolution_notes? }`, plus this item's `recording_id`/`transcript_id` (Drive
source) and `source_meeting` label (local source — a label, not a file, since no local meeting
page exists).

## Skip Condition

If `reconciled_type == "duplicate"`: **write nothing**. No decision file, no feature-request
edit. Log it as `duplicates_skipped` for the run report and stop here — `wiki-index-updater.md`
and `wiki-ticket-creator.md` never run for this item.

## Steps (for every non-duplicate item)

1. **Assign `DEC-NNNN`.** Scan `decisions/DEC-*.md` for the current max number, increment,
   zero-pad. Never reuse or renumber an existing id.
2. **Write `decisions/DEC-NNNN_<slug>.md`** per `wiki/SCHEMA.md`'s exact frontmatter and section
   format: `title`, `date`, `id`, `feature` (or `null`), `source_meeting`, `recording_id`,
   `transcript_id`, `type: <reconciled_type>`, `evidence_quote`, the full `reconciliation` block,
   `supersedes` (if set), `linear_issue: null` (filled in later by `wiki-ticket-creator.md`).
   Body: `## Statement` (one clear sentence) and `## Reconciliation Notes` (1–3 sentences,
   including anything from `wiki-resolution-handler.md`'s `resolution_notes` if present).
3. **If `supersedes` is set:** edit the referenced old `DEC-NNNN` file to add
   `superseded_by: <new DEC-NNNN>` — this is the *one* permitted edit to an otherwise write-once
   decision record. Nothing else about the old record changes.
4. **Update the feature request** (skip this step entirely if `feature` is `null`):
   `feature-requests/{feature}/feature-request.md` — edit only the sections this decision
   actually changes:
   - New/changed **Current State**, **Key Facts**, **Requirements**, or **Business Rules**: trim
     or replace the stale line and link this `DEC-NNNN` — never just append forever. If the
     decision reopens or resolves an **Open Question**, move it to the "Resolved" list with a
     link to this `DEC-NNNN`, or add a new open question if this decision surfaces one.
   - Always add a row to the feature's `## Decisions` table and a link under `## Evidence` — both
     are thin indexes (links/one-liners only, per `wiki/SCHEMA.md`) — never restate the
     `## Statement` there.
   - Update `last_updated` in the frontmatter.

## Output

`{ dec_id: "DEC-NNNN", feature: string | null, decision_file: path, feature_file: path | null }`
— passed to `wiki-index-updater.md` next.

## Rules

- Decision records are **write-once**, with exactly one permitted exception: adding
  `superseded_by` to an old record when a new one explicitly supersedes it (Step 3). Nothing else
  about an existing `DEC-NNNN` file is ever edited after creation.
- Feature-request current-state sections are **trimmed/replaced**, never append-forever — re-read
  `wiki/SCHEMA.md`'s Current-State vs. Immutable-Ledger discipline before editing one.
- `## Decisions`/`## Evidence` on a feature-request page are links only — never copy a
  transcript excerpt or restate a `## Statement` there.
- Every section heading in `feature-request.md` stays present even when empty
  ("Nothing recorded yet.") — never omit a heading.
- `duplicate` items produce absolutely nothing — verify the skip condition before doing any other
  work for an item.
