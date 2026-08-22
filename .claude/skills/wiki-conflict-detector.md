# wiki-conflict-detector

The authoritative reconciliation step. Everything before this point (classification, feature
mapping) was a first pass from text alone; this step is the only one that actually looks at
`wiki/{project-id}/decisions/` history, and it can upgrade or downgrade what
`wiki-decision-classifier.md` assigned.

## Input

An item `{ summary, evidence_quote, type, feature }` (feature may be `null`), plus the **entire**
`wiki/{project-id}/decisions/` tree — every decision ever written for this project, not narrowed
to just the item's mapped feature. Two different feature requests can still contradict or
duplicate each other, so the scan is always project-wide.

## The Six Reconciliation Questions

For this item, determine:

1. `existed_before` — has an equivalent decision already been recorded (same substance, possibly
   different wording)?
2. `previously_rejected` — was this same approach explicitly rejected before (a `rejected`-type
   decision on the same topic)?
3. `contradicts` — does this item conflict with the substance of any existing decision? List the
   specific `DEC-NNNN` id(s).
4. `on_roadmap` — is this already reflected in a feature request's current-state sections (i.e.
   already "true" per the wiki, just being re-confirmed rather than newly decided)?
5. `dependencies` — does this item depend on other decisions or tickets? List `DEC-NNNN` ids or
   ticket ids.
6. `changes_plan` — does this item change something a feature request's Current State/Requirements/
   Business Rules currently says is true?

## Reconciled Type

Based on the six answers, determine `reconciled_type` — which may differ from
`wiki-decision-classifier.md`'s raw `type`:

- **`duplicate`** — `existed_before` is true with no material difference from an existing
  decision of the same type. This is the **only** outcome that produces no decision file and no
  ticket (see `wiki-writer.md`).
- **`superseded`** (upgrade from `decided`/`rejected`) — `changes_plan` is true and this item
  clearly overrides a specific earlier decision. Record which `DEC-NNNN` it supersedes.
- **Raw type unchanged** — none of the above apply; carry `wiki-decision-classifier.md`'s `type`
  through as `reconciled_type`.

If `contradicts` is non-empty and the conflict isn't a clean supersession (i.e. it's a genuine,
unresolved tension rather than one decision clearly replacing another), flag `needs_resolution:
true` — `wiki-resolution-handler.md` runs next.

## Output

`{ ...item, reconciliation: { existed_before, previously_rejected, contradicts, on_roadmap, dependencies, changes_plan }, reconciled_type, needs_resolution: bool }`

## Rules

- **Always scan the whole project's decision history**, never narrow to just the item's mapped
  feature — a `feature: null` item or a cross-feature contradiction would otherwise be invisible.
- This is the only step allowed to assign `duplicate` or upgrade a raw classification to
  `superseded` — no earlier step should attempt this.
- `needs_resolution: true` pauses the pipeline for this item (`wiki-resolution-handler.md`) before
  `wiki-writer.md` runs — never write a decision record while an unresolved contradiction is
  flagged.
- Like the confidence-scoring steps earlier in this pipeline, reconciliation is calibrated LLM
  judgment against a written rubric, not a deterministic diff — treat its output accordingly and
  keep the six questions' definitions stable so judgments stay consistent across runs.
