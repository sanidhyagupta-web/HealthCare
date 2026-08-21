# Eval Case 07 — Prompt

Paste this verbatim into a fresh Claude Code / Cursor session after loading `AiHarness/Agents.md`.

---
Firstly read `Agents.md`.

Harmony currently allows the same document to be uploaded and fully re-ingested multiple times, bloating the Chroma store with duplicate chunks and polluting search results with repeated content.

Add duplicate detection at two levels:

**Level 1 — Document-level deduplication:**
- When a new document is submitted for ingestion, compute a SHA-256 hash of the raw file bytes before any parsing.
- Check whether a document with the same file hash already exists in `DocumentRegistry` with `DocStatus.INDEXED`.
- If a duplicate is found, set the new document's status to `DocStatus.DUPLICATE` immediately and emit a `DOC_DUPLICATE` audit event with the original `doc_id` in `details`. Do not enqueue it for parsing.
- Store the file hash in a new `file_hash` column on the `DocumentRegistry` table.

**Level 2 — Chunk-level deduplication (already partially implemented):**
- Confirm that `ChunkingWorker` calls `register_chunk()` which deduplicates via SHA-256 of normalized chunk text.
- If all chunks of a document are duplicates of previously indexed chunks, set `DocStatus.DUPLICATE` on the document.
- This path must not leave orphaned chunks in the Chroma store.

Add a `GET /admin/duplicate-documents` endpoint that lists all documents with `DocStatus.DUPLICATE`, showing `doc_id`, `source_file`, `uploaded_at`, and `original_doc_id`. Admin role only.

Build this feature.

After building this feature compare the output with `expected.md` and write down the results in `result-notes.md`.
