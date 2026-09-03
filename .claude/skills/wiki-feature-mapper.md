# wiki-feature-mapper

Matches each classified item against this project's known feature requests
(`feature-requests/index.md`) — the one-level-down equivalent of what the old multi-project
design used a project-mapper for, now scoped within this single project.

## Input

A classified item `{ summary, evidence_quote, topics_mentioned, type }` from
`wiki-decision-classifier.md`, plus `wiki/{project-id}/feature-requests/index.md`.

## Steps

1. Read `feature-requests/index.md` for the current catalog of known feature-request ids and
   summaries.
2. Compare the item's `topics_mentioned` and `summary` against each known feature request's
   summary. This is judgment (an LLM reading both descriptions and deciding how well they match),
   not a similarity algorithm.
3. Score confidence 0.0–1.0 for the best-matching feature request.
4. Apply the same hard threshold used throughout this pipeline: **confidence ≥ 0.55** is a match.
   Below that:
   - If the item clearly concerns *some* coherent capability that just isn't in the catalog yet,
     flag `new_feature_candidate: true` with a proposed `id`/`title`.
   - If it plausibly matches an existing feature request under different wording (e.g. "the
     export thing" vs. registered `billing-export`), flag
     `possible_alias_of: "<feature-id>"` instead.
   - If there's no signal at all — genuinely ambiguous, not clearly anything — leave both flags
     unset; the item proceeds with `feature: null` and skips `wiki-feature-onboarder.md`
     entirely.

## Output

`{ ...item, feature: "<feature-id>" | null, confidence: float, new_feature_candidate?: {...}, possible_alias_of?: string }`

- `feature` set (confidence ≥ 0.55) → proceeds directly to `wiki-conflict-detector.md`.
- `new_feature_candidate` or `possible_alias_of` set → `wiki-feature-onboarder.md` runs next.
- Neither set → proceeds with `feature: null` directly to `wiki-conflict-detector.md`.

## Rules

- **Never guess.** Below 0.55 confidence, `feature` is `null` — always flag *why* it's unmatched
  (candidate vs. alias vs. no signal) so `wiki-feature-onboarder.md` (or a human, later, reading
  the decision record) can act on the specific reason.
- This step runs per **classified item**, not per raw meeting segment — one meeting can produce
  several items mapping to different features, or none.
- A `feature: null` item is not an error — it still gets a full decision record via
  `wiki-writer.md`; `feature: null` is itself meaningful information (this decision isn't tied to
  any known capability yet).
