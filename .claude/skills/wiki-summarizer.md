# wiki-summarizer

Extracts the substance of a relevant item so every downstream step works from structured signal
instead of re-reading raw transcript text each time.

## Input

`{ id, sanitized_text }` for an item `wiki-relevance-checker.md` marked relevant.

## Steps

1. Read the full sanitized text.
2. Extract every discrete **discussion item** — a decision made, a question left open, an
   approach explicitly rejected, or a prior decision explicitly changed/superseded. Each becomes
   one candidate item for the rest of the pipeline; don't merge distinct topics into one, and
   don't split one continuous discussion into artificial duplicates.
3. For each item, extract:
   - `summary` — one or two sentences, plain language.
   - `evidence_quote` — the verbatim line(s) grounding it, quoted exactly from the
     `[EVIDENCE]`-wrapped text (never paraphrased — this is what `wiki-writer.md` later puts in
     the decision record's `evidence_quote` field).
   - `topics_mentioned` — keywords/phrases useful for `wiki-feature-mapper.md`'s later matching
     (feature names, component names, anything that hints which capability this concerns).
4. Extract action items separately if present (owner, what, by when) — these aren't decisions by
   themselves, but note them if they relate to a decision item (e.g. "ship the export by Friday"
   attached to a `decided` item about the export feature).
5. Extract key facts that aren't decisions or action items but are useful context (e.g. a stated
   constraint, a metric mentioned) — these can end up in a feature's `## Key Facts` section later.

## Output

For the item: a list of `{ summary, evidence_quote, topics_mentioned, related_action_items }`
entries — one per discussion item found. An item with no discrete discussion items (e.g. a
purely social/logistics meeting) produces an empty list, which the orchestrator treats the same
as `not_relevant` for reporting purposes — no decision, no ticket.

## Rules

- `evidence_quote` must be copied verbatim from the sanitized text — never paraphrase it. The
  decision record's whole point is to ground a decision in what was actually said, not a
  restatement.
- Don't invent decisions that weren't discussed — if a meeting was inconclusive on a topic, that's
  an `unresolved` classification later (via `wiki-decision-classifier.md`), not a fabricated
  `decided` item.
- One discussion item per candidate — don't bundle "we decided X and also Y" into a single item
  if X and Y are separable decisions; `wiki-conflict-detector.md` and `wiki-feature-mapper.md`
  later need to reason about each independently.
