# wiki-feature-onboarder

Runs only when `wiki-feature-mapper.md` flags an item `new_feature_candidate` or
`possible_alias_of`. **Never renames or merges an existing feature request without a human
deciding** — but see "Non-interactive runs" below for what "a human deciding" means when there
is no one to prompt, because that is not the same thing as "never writes anything".

## Input

An item from `wiki-feature-mapper.md` carrying `new_feature_candidate: { id, title }` or
`possible_alias_of: "<feature-id>"`.

## Non-interactive runs (the webhook-triggered ticket path)

`AskUserQuestion` does not exist in a headless sortie. That does **not** make this skill a
dead end there, and treating it as one is what made the first ticket on a fresh project
unrecordable: with an empty `feature-requests/index.md` every ticket is a
`new_feature_candidate`, so every ticket reached a step that could not run, so the wiki was
never built — and it is supposed to be built forward, ticket by ticket, by exactly this path.

**What the rule actually requires is that a human decides — not that a human is prompted.**
On the ticket path there are two channels the meeting-ingest pipeline never had: the Linear
ticket itself (a bot comment plus the `open-questions` label and its reply window), and the
**wiki pull request**, which a human reviews before anything merges. A feature request created
in an unmerged PR is a proposal on the record, not a fact in the wiki. That is a stronger form
of asking than a prompt, because it leaves an artifact the reviewer can act on later.

So the split below is by **whether the write is additive or mutating**, not by whether a human
is present:

| Flag | Nature | Headless behaviour |
|---|---|---|
| `new_feature_candidate` | **Additive** — creates a record that did not exist. A wrong id costs a rename. | **Create it.** Case 1(a) below, plus the marking rules here. |
| `possible_alias_of` | **Mutating** — merges this item into an existing feature, or renames one. Not reversible by a rename. | **Do not alias.** Create it as a distinct feature request and flag the suspected alias. |

When you create headlessly, all three of these are required — the create is only defensible
because they make it reviewable:

1. Set `proposed_by: agent` and `identity_confirmed: false` in the new
   `feature-request.md`'s frontmatter, so a later reader can tell an agent's proposal from a
   human's own feature request without reading git history.
2. Write the identity question into that file's `## Open Questions` verbatim — for a
   `new_feature_candidate`: *"Is `{id}` the right feature request for this work, or does it
   belong to an existing one? Created by an agent from ticket `{ticket}`; rename or merge if
   wrong."* For a `possible_alias_of`: *"This may be the same feature as `{feature-id}` under
   different wording. Created as distinct rather than merged, because merging cannot be undone
   by a rename. Confirm or merge."*
3. State it in the PR description too, not only in the file. The reviewer's decision is the
   approval this skill would otherwise have prompted for, and they cannot give it to a
   question buried in a diff.

**Never resolve a contradiction headlessly.** `wiki-resolution-handler.md` rewrites existing
content, which is mutating in the strongest sense — if that is reached with no human, stop and
report the unanswered question, exactly as before.

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

- **Never alias, merge or rename an existing feature request without a human deciding.** That
  judgment call always goes to a human regardless of how confident the model feels, because it
  is not reversible by a rename. Interactively that means `AskUserQuestion`; headlessly it means
  do not do it at all — create a distinct feature request and flag the suspicion.
- **Creating** a new feature request headlessly is allowed, and required for the ticket path to
  work at all, but only under the three marking rules in "Non-interactive runs" above.
  `proposed_by: agent` plus an unanswered question in the file plus the same question in the PR
  body is what makes it a proposal under review rather than an invented fact.
- Ask about one item at a time — don't batch multiple onboarding decisions into a single prompt,
  since each answer can change what's "existing" for the next one (a newly created feature
  request should be offered as a match option for subsequent items in the same run).
- A declined/unassigned item is not an error — it still gets a full decision record via
  `wiki-writer.md`, with `feature: null`. There is no separate log or "pending onboarding" file —
  the decision record's `feature: null` field is the only record of the outcome.
