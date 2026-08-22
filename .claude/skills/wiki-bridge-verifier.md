# wiki-bridge-verifier

Cross-checks a claimed FR ↔ FEAT link between product-wiki (intent) and code-wiki (reality) — the
connector `/init-code-wiki`'s Step 5c calls after writing a `Feat-NNNN-{feature-id}/Index.md`
whose `implements:` frontmatter names an `FR-*`, or that traces back to a `DEC-NNNN` with a
non-null `feature:` field. It doesn't live inside either
tree: a feature-request doesn't know whether it's been built, and a FEAT doesn't know what intent
it satisfies, without something that reads both sides and judges the match.

## Input

- `fr_requirements`: the `## Requirements` list from `wiki/{project-id}/feature-requests/{feature-id}/feature-request.md`
- `fr_business_rules`: the same file's `## Business Rules` list
- `feat_content`: the `## Business Rules` and `## Key Flows` sections just written into
  `code-wiki/{project-id}/Features/Feat-NNNN-{feature-id}/Index.md`
- `feature_id`, `dec_id` — for labeling the output only, not used in the judgment itself

## Steps

1. For each item in `fr_requirements` and `fr_business_rules`, read `feat_content` and judge
   whether it describes matching behavior. This is calibrated LLM judgment — reading both
   descriptions and deciding whether the shipped behavior actually satisfies the stated intent —
   not a keyword or string match. A paraphrase counts as a match; a requirement with no
   corresponding behavior, or behavior that contradicts it, does not.
2. Classify each item: `satisfied` (matching behavior found), `contradicted` (FEAT content
   describes something that conflicts with the requirement), or `no_match` (nothing in
   `feat_content` addresses it).
3. Roll up an overall verdict from the per-item classifications:
   - **`verified`** — every item is `satisfied`.
   - **`partial`** — at least one `satisfied`, at least one `no_match`/`contradicted`.
   - **`unmatched`** — every item is `no_match` or `contradicted` (nothing landed).
4. Write a one-line `summary` — for `partial`/`unmatched`, name the specific unmet or
   contradicted item(s); don't just say "some requirements not met."

## Output

```
{
  verdict: "verified" | "partial" | "unmatched",
  per_item: [{ text, status: "satisfied" | "contradicted" | "no_match" }],
  summary: "<one line>"
}
```

## Rules

- **Never mark `verified` on partial evidence.** If even one requirement or business rule has no
  matching behavior in `feat_content`, the verdict is at most `partial` — this check exists to
  surface exactly that gap, not to rubber-stamp a link because most of it lines up.
- **Never infer a match from naming alone** (e.g. a FEAT and FR sharing a similar title) — the
  judgment is against the actual requirement/business-rule text vs. the actual documented
  behavior, every time.
- This is advisory, not a gate — the caller (`/init-code-wiki` Step 5c) always writes the
  verdict into both `Feat-NNNN-{feature-id}/Index.md` and the decision's `implemented_by` field
  regardless of outcome; it never withholds the link because the verdict came back `partial` or
  `unmatched`. Silence would hide the exact signal a human needs.
- A `no_match` item is not evidence of missing code — it may mean the requirement was addressed
  elsewhere (a different feature, a shared library) or genuinely dropped. This step reports the
  gap; it doesn't diagnose the cause.
