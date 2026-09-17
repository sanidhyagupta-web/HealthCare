# wiki-transcript-reader

Drive-only step, run after `wiki-drive-scanner.md` for items whose mime type is a raw transcript
format (VTT, SRT, or a Gemini meeting-notes doc with an embedded transcript section) rather than
already-clean text. Local fixtures (`inbox/`) skip this step entirely.

## Input

- `drive_file_id` for the item.
- The `claude.ai Google Drive` MCP tools (`download_file_content`, `read_file_content`).

## Steps

1. Download/read the file content.
2. Strip transcript-format artifacts that carry no meaning for the pipeline: VTT/SRT timestamp
   lines and cue numbers, speaker-diarization noise (`[inaudible]`, repeated filler markers),
   duplicate consecutive lines from caption auto-repetition.
3. Preserve speaker labels and turn boundaries — `wiki-summarizer.md` later needs "who said what"
   to ground `evidence_quote` fields accurately.
4. Collapse the result into clean, readable text — paragraphs per speaker turn, not raw caption
   blocks.

## Output

`{ id, source: "drive", raw_text }` — same shape a local fixture already has. From here,
`wiki-sanitizer.md` treats both sources identically.

## Rules

- Never summarize or drop content here — this step only removes format noise (timestamps, cue
  numbers), never meaning. Summarization is `wiki-summarizer.md`'s job, later in the pipeline.
- Never invent a speaker label that wasn't in the source — if diarization is missing or unclear,
  leave the turn unattributed rather than guessing who said it.
