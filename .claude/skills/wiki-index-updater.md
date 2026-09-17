# wiki-index-updater

Keeps the two catalog files in sync with what `wiki-writer.md` just wrote — surgical edits only,
never a full regeneration.

## Input

`{ dec_id, feature, decision_file, feature_file }` from `wiki-writer.md`. Skipped entirely for
`duplicate` items (which never reach here).

## Steps

1. **`decisions/index.md`** — append one row: `DEC-NNNN`, date, title, `reconciled_type`, mapped
   feature (linked, or blank if `null`), ticket link (blank for now — `wiki-ticket-creator.md`
   fills this in next and may need to come back and edit this same row).
2. **`feature-requests/index.md`** — if this decision touched a feature (`feature` is not `null`):
   update that feature's row — `Summary` (only if this decision meaningfully changed what the
   one-line summary should say), `Status` (`active`/`deprecated`, only if this decision changes
   it), `Open Questions` (recompute the count from the feature's current `## Open Questions`
   section), `Last Touched` (today's date). If this was a newly-created feature (via
   `wiki-feature-onboarder.md`), add its row instead of updating an existing one.

## Output

Confirmation that both index files are current — no data returned beyond that; the item proceeds
to `wiki-ticket-creator.md`.

## Rules

- **Never rewrite existing rows wholesale** — edit only the fields this specific decision
  actually changes. A full regeneration risks losing a hand-edited field or another decision's
  concurrent update within the same run.
- Keep `decisions/index.md` in strict `DEC-NNNN` order — append at the end, never reorder
  existing rows.
- If a decision's ticket link needs to be added after `wiki-ticket-creator.md` runs, that's a
  small follow-up edit to the same row this step just added — not a reason to defer this whole
  step until after ticket creation.
