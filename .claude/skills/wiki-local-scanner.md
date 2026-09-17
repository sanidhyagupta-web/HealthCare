# wiki-local-scanner

Invoked by `wiki-ingest/SKILL.md` Step 5 when the source is `local`. Scans `inbox/` at the repo
root for fake meeting-drop fixtures — a stand-in for Google Drive so the pipeline can be tested
without touching a real Drive folder.

## Input

- `inbox/` — one `.md` file per fake meeting, Gemini-notes style (title line, attendee list,
  timestamped speaker turns). See `inbox/README.md` for fixture conventions if present.
- `wiki/{project-id}/processed.json` — durable ledger of already-processed item IDs.

## Steps

1. List every `.md` file directly under `inbox/` (non-recursive — fixtures are flat files, not
   nested).
2. Derive each item's `id` deterministically from its filename (e.g.
   `2026-07-14-standup.md` → id `2026-07-14-standup`). Renaming a fixture file is how you make the
   pipeline reprocess similar content — the id is filename-derived, not content-hashed.
3. Read `wiki/{project-id}/processed.json`. Filter out any `id` already present as a key there.
4. For each remaining file, read its full text — no transcript-cleaning step is needed (local
   fixtures are already plain text), so these items skip `wiki-transcript-reader.md` entirely and
   go straight to `wiki-sanitizer.md`.

## Output

A list of unprocessed items, each `{ id, source: "local", raw_text, file_path }` — this shape
matches exactly what `wiki-drive-scanner.md` produces, so every downstream step is source-agnostic.

## Rules

- Never process a file whose `id` already exists in `wiki/{project-id}/processed.json` — that
  check is what makes re-running `/wiki-ingest local` a no-op after a successful pass.
- Never recurse into subdirectories of `inbox/` — fixtures are flat files only.
- Don't invent content for a malformed fixture — if a file is empty or unreadable, log it and
  skip it (surfaced later as a `failed` item by the orchestrator), don't guess at what it might
  have said.
