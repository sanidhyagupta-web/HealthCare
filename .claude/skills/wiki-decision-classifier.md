# wiki-decision-classifier

Tags each discussion item from `wiki-summarizer.md` with one of four types, from text alone — no
wiki lookup happens here (that's `wiki-conflict-detector.md`'s job, later, which can still
override this tag).

## Input

One `{ summary, evidence_quote, topics_mentioned }` item from `wiki-summarizer.md`.

## Classification Rubric

- **`decided`** — a clear, affirmative choice was made. Signal phrases: "we're going with...",
  "let's do...", "decided to...", "agreed that...".
- **`unresolved`** — the topic was discussed but no choice was made. Signal phrases: "we still
  need to figure out...", "TBD", "let's revisit...", explicit disagreement with no resolution
  reached in this meeting.
- **`rejected`** — an approach was explicitly considered and turned down. Signal phrases: "we're
  not going to...", "we decided against...", "ruled out...". Distinguish from `unresolved` — a
  rejection is a decision (to not do something), not an open question.
- **`superseded`** — the meeting explicitly overturns or replaces a decision made in an earlier
  meeting. Signal phrases: "actually, we're changing course from...", "revisiting our earlier
  decision on...". This classification alone doesn't know what specifically it supersedes yet —
  that gets resolved in `wiki-conflict-detector.md`'s reconciliation pass against
  `decisions/` history.

## Steps

1. Read the item's `summary` and `evidence_quote`.
2. Match against the rubric above. This is judgment, not keyword matching — the signal phrases
   are illustrative, not exhaustive; read for intent.
3. When genuinely ambiguous between two types (e.g. reads as `decided` but is stated tentatively),
   default to the more conservative one — `unresolved` over `decided`, since a decision record
   wrongly marked `decided` propagates further (a ticket gets created with a `decided`-style
   actionable template) than one correctly marked `unresolved`.

## Output

`{ ...item, type: "decided" | "unresolved" | "rejected" | "superseded" }`

## Rules

- This is a text-only judgment — never consult `decisions/` history here to "check if this
  matches"; that's `wiki-conflict-detector.md`'s explicit job, one step later, and duplicating it
  here would just create two sources of truth for the same reconciliation logic.
- `duplicate` is never assigned by this step — it's a `wiki-conflict-detector.md` **reconciliation
  outcome**, not a raw classification. This classifier's four types are the only possible outputs
  here.
- When uncertain, prefer the more conservative type (see Step 3) rather than guessing confidently.
