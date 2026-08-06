# wiki-relevance-checker

Single-project replacement for what used to be a multi-project mapping step. This repo's wiki
only ever belongs to one project (`WIKI_PROJECT_ID`/`WIKI_PROJECT_NAME` in
`.claude/wiki-project.env`), so there's nothing to *match against* — the only question is whether
this particular meeting/segment is actually about this project at all, or is unrelated noise
(a different team's standup accidentally dropped in the same Drive folder, an all-hands with no
project-specific content, etc.).

## Input

`{ id, sanitized_text }` from `wiki-sanitizer.md`, plus `WIKI_PROJECT_NAME` and
`WIKI_PROJECT_ALIASES` (comma-separated nicknames the project might be called in conversation)
from `.claude/wiki-project.env`.

## Steps

1. Read the sanitized text. Look for direct signal: the project name or any alias mentioned by
   name, discussion of features/APIs/architecture that match this project's known domain
   (cross-reference `docs/features/` or `code-wiki/` if unsure), attendees known to work on this
   project.
2. Score confidence 0.0–1.0 based on how directly the content ties to this project. This is a
   judgment call, not a trained classifier — an LLM reading the rubric, same as the equivalent
   confidence scoring in `wiki-feature-mapper.md` and `wiki-conflict-detector.md`.
3. Apply the same hard threshold used everywhere else in this pipeline: **confidence ≥ 0.55** is
   relevant, below it is not. Err conservative when uncertain — a false negative here just means
   one meeting doesn't contribute (recoverable, re-processable if it's later found relevant by
   renaming the fixture / re-scanning); a false positive pollutes the wiki with unrelated content
   that a human later has to notice and clean up.

## Output

`{ id, relevant: bool, confidence: float, reason: string }`

- `relevant: true` → the item proceeds to `wiki-summarizer.md`.
- `relevant: false` → the orchestrator marks this item `status: "not_relevant"` in
  `wiki/{project-id}/processed.json` and moves on. This is not a failure and is not logged as an
  error — it's a normal, expected outcome for a meeting that happens to share a Drive folder or
  inbox with this project's real content.

## Rules

- Never skip this check because "it came from the configured Drive folder / inbox, so it must be
  relevant" — a shared inbox or Drive folder does not guarantee every item belongs to this
  project.
- Never guess when signal is genuinely absent — mark `relevant: false` rather than assuming yes.
- This step has no "ask the user" branch (unlike `wiki-feature-onboarder.md`) — relevance is a
  binary in/out gate for this run, not a registry decision that needs confirmation. If a whole
  category of meetings is being wrongly excluded, that's a threshold-tuning conversation for
  `.claude/wiki-project.env`'s `WIKI_PROJECT_ALIASES`, not a per-item interactive prompt.
