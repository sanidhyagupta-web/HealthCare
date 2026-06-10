# Eval Case 05 — Prompt

Paste this verbatim into a fresh Claude Code / Cursor session after loading `AiHarness/Agents.md`.

---
Firstly read `Agents.md`.

The team wants to evaluate whether upgrading from `all-MiniLM-L6-v2` (384 dimensions) to `all-mpnet-base-v2` (768 dimensions) improves retrieval quality for clinical queries. This is a breaking change — the new model produces vectors of a different size, so the existing Chroma collection cannot be reused.

Make the model configurable and perform the swap:
- Move the embedding model name and vector dimension into `app/config.py` (or `settings.py`) as `settings.embedding_model` and `settings.embedding_dim`. Do not hardcode either value anywhere else.
- Update `indexing/embeddings.py` to load the model from `settings.embedding_model` at startup (not per-call).
- Update `indexing/chroma_store.py` so the Chroma collection name includes the model name (e.g., `harmony_chunks_all-mpnet-base-v2`) to prevent dimension mismatches between old and new collections.
- Provide a migration script `scripts/reindex.py` that re-embeds all `DocStatus.INDEXED` documents using the new model and upserts them into the new collection. The script must not re-parse or re-chunk — it reads existing chunks from the database and calls `embed_texts()` directly.
- Update `evaluation/run_eval.py` to assert that the configured model name matches the collection name on every eval run — fail loudly if they diverge.

Do not delete the old collection automatically. Log a warning if the old collection exists alongside the new one.

Build this feature.

After building this feature compare the output with `expected.md` and write down the results in `result-notes.md`.
