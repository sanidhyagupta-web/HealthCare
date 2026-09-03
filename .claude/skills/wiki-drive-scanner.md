# wiki-drive-scanner

Invoked by `wiki-ingest/SKILL.md` Step 5 when the source is `drive`. Scans the Google Drive folder
at `DRIVE_FOLDER_ID` (`.claude/wiki-project.env`) for meeting recordings/notes (Gemini meeting
notes, typically a transcript file plus a companion notes doc per meeting).

## Input

- `DRIVE_FOLDER_ID` from `.claude/wiki-project.env`.
- `wiki/{project-id}/processed.json` — durable ledger of already-processed item IDs.
- The `claude.ai Google Drive` MCP tools (`list_recent_files`, `search_files`,
  `get_file_metadata`, `download_file_content`, `read_file_content`).

## Steps

1. List files under `DRIVE_FOLDER_ID` (non-recursive, unless the folder structure requires
   otherwise — confirm with the user if the folder contains unexpected subfolders rather than
   guessing whether to recurse).
2. Derive each item's `id` from the Drive file's stable ID (`file_id`), not its display name —
   Drive filenames can be renamed without changing identity, and the id must stay stable across
   runs for `processed.json` to work.
3. Read `wiki/{project-id}/processed.json`. Filter out any `id` already present as a key there.
4. For each remaining file, fetch its metadata (mime type, name, modified time) — this determines
   whether it needs `wiki-transcript-reader.md` (raw VTT/SRT/transcript files) or is already
   plain text (a notes doc).

## Output

A list of unprocessed items, each `{ id, source: "drive", drive_file_id, mime_type, file_path: null }`
— downstream steps fetch content via `wiki-transcript-reader.md` (transcripts) or direct
`download_file_content`/`read_file_content` (notes docs), producing the same
`{ id, source, raw_text }` shape `wiki-local-scanner.md` produces before sanitization.

## Rules

- Never process a Drive file whose `id` already exists in `wiki/{project-id}/processed.json`.
- If Drive access fails (auth, permissions, folder not found), **stop and tell the user** — don't
  silently fall back to `local` or report "up to date" when the real answer is "couldn't check."
- Don't guess at a file's relevance from its name alone — download and let
  `wiki-relevance-checker.md` (later in the pipeline) make that call from actual content.
