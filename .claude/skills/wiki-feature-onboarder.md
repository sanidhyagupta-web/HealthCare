# wiki-feature-onboarder

Runs only when `wiki-feature-mapper.md` flags an item `new_feature_candidate` or
`possible_alias_of` — never automatically creates or renames a feature request without asking.

## Input

An item from `wiki-feature-mapper.md` carrying `new_feature_candidate: { id, title }` or
`possible_alias_of: "<feature-id>"`.

## Steps

1. **`new_feature_candidate`** — use `AskUserQuestion` to confirm: show the item's `summary` and
   `evidence_quote`, the proposed feature-request `id`/`title`, and ask whether to (a) create this
   new feature request, (b) actually resolve it to an existing feature request instead (offer the
   closest existing matches from `feature-requests/index.md` as options), or (c) leave it
   unassigned (`feature: null`) for this item.
   - **(a) Create** — bootstrap `feature-requests/{id}/feature-request.md` per `wiki/SCHEMA.md`'s
     template (empty Current State/Key Facts/Requirements/etc. sections, all reading "Nothing
     recorded yet." until `wiki-writer.md` fills them from this item), and add a row to
     `feature-requests/index.md` via `wiki-index-updater.md`. Return `{ feature: id }` for this
     item.
   - **(b) Resolve to existing** — return `{ feature: <chosen existing id> }`.
   - **(c) Leave unassigned** — return `{ feature: null }`.
2. **`possible_alias_of`** — use `AskUserQuestion` to confirm: is this really the same feature
   request under different wording, or a genuinely distinct one that happens to sound similar?
   - **Same feature** — return `{ feature: <that feature-id> }`.
   - **Distinct, new feature** — treat as case 1(a) above.
   - **Leave unassigned** — return `{ feature: null }`.

## Output

`{ ...item, feature: "<feature-id>" | null }` — same shape `wiki-feature-mapper.md` produces for a
confidently-matched item, so `wiki-conflict-detector.md` (next) doesn't need to know whether the
match came from confidence or a human confirmation.

## Rules

- **Never create or alias a feature request without asking** — this is the one place in the
  pipeline where an ambiguous judgment call always goes to a human, never resolved automatically
  regardless of how confident the model feels.
- Ask about one item at a time — don't batch multiple onboarding decisions into a single prompt,
  since each answer can change what's "existing" for the next one (a newly created feature
  request should be offered as a match option for subsequent items in the same run).
- A declined/unassigned item is not an error — it still gets a full decision record via
  `wiki-writer.md`, with `feature: null`. There is no separate log or "pending onboarding" file —
  the decision record's `feature: null` field is the only record of the outcome.
