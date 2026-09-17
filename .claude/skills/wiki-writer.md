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
   **Both go straight into a Linear ticket — see "Product language, not technical language" below
   before writing either.** Rewrite `resolution_notes` to that standard rather than pasting it: it
   arrives as reasoning, and what the ticket needs is behaviour.
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

## Product language, not technical language

`## Current State`, `## Key Facts`, `## Requirements` and `## Business Rules` are read by product
managers and business stakeholders, and a Linear ticket's Acceptance Criteria is built **verbatim**
from `## Requirements`. Write all four as screens, user-visible workflows and business rules: what a
person is trying to do, what they see, and what the product must guarantee.

**Those four sections may not name a file, directory, function, class, method, module, package,
database table, column, environment variable, or any other code identifier.** Naming a product
surface is required — "the booking cancellation screen", "the checkout flow", "the invitation email".
Naming code is forbidden. If something can only be said by naming code, it is a statement about the
implementation and does not belong in a feature request at all; the technical approach is derived
later, from the codebase itself, by whoever implements it.

Link tables — `## Decisions`, `## Evidence`, `## Relationships` — are unaffected. A `DEC-NNNN` id or
a code-wiki link is a reference, not a code identifier.

### The decision record's own prose is held to the same standard

`DEC-NNNN`'s `## Statement` and `## Reconciliation Notes` are not internal notes — **both are read
straight into the Linear ticket a product manager and an assignee work from.** `## Statement`
becomes the ticket's `## Summary`; `## Reconciliation Notes` becomes its
`## Existing System Behavior`. Neither is paraphrased on the way, so whatever is written here is
what they read. Apply the no-code-identifiers rule above to both.

**Never quote the transcript in either of them.** The verbatim line has exactly one home — the
record's own `evidence_quote` field — and that field is deliberately *not* carried into the ticket,
because transcript text in a ticket every assignee reads was ruled unwanted rather than merely
optional. Re-quoting the same words inside `## Statement` or `## Reconciliation Notes` puts them in
the ticket anyway, by a side door, and defeats the rule without appearing to break it. Say what was
decided, in your own words; the quote is already recorded one field above.

**Write `## Reconciliation Notes` as behaviour, not as bookkeeping.** It is the answer to "what does
the product do today, and how does this change it" — not a report on this run's own reasoning. Do
not restate the `reconciliation` frontmatter in prose (`existed_before`/`on_roadmap`/`changes_plan`
are already there, structured, and a reader who wants them can read them), do not narrate what this
skill checked or which branch it took, and do not name the resolution rules it followed.

**Start with today's behaviour, in every case.** The first sentence must say what a person can and
cannot do in the product right now, in the area this decision touches — "Booking the same room and
slot every week means creating each week's booking by hand, one at a time." That sentence is the
reason the section exists, and it is the one thing the person holding the ticket cannot get anywhere
else.

⚠ **Never write a sentence whose content is "nothing conflicts."** "This establishes a new
capability with no prior decision to conflict with", "introduces no conflict with any prior
decision", "no prior decision addressed this" — all of these are answers to a question the reader
did not ask, and a section made of them tells them nothing at all. The absence of a conflict is not
news; it is the default. If there is genuinely no conflict, the section is *just* today's behaviour
and then it stops. One or two sentences is a complete section.

**Where a genuine conflict does exist**, describe the two behaviours that disagree, in product
terms, and what a person has to choose between — that is the case where this section earns more than
a sentence, and it is worth the space.

**Why this rule is here and not only in `wiki/SCHEMA.md`.** That file is written once per `wiki/`
tree by a one-time scaffold (`init-product-wiki`), which stops if the project is already scaffolded —
so a repository scaffolded before this rule existed never receives it. Carrying the rule in the
skills that actually write feature requests is what makes it apply everywhere. The duplication is
deliberate; do not remove it in favour of the template.

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
