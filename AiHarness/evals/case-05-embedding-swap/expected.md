# Eval Case 05 — Expected Output

## Templates
- [ ] `features/active/embedding-swap/01-product-spec.md` created and filled:
  - User: ML engineer / platform team
  - Problem: `all-MiniLM-L6-v2` (384-dim) may be undersized for long clinical narratives; `all-mpnet-base-v2` (768-dim) is a candidate upgrade
  - Success criteria include: swap is config-driven (no code change needed for future model changes), old collection not deleted, eval pipeline verifies model/collection alignment, reindex script runs without re-parsing
  - Out of scope: fine-tuning, cloud embedding APIs, automatic A/B testing

- [ ] `features/active/embedding-swap/02-technical-spec.md` created and filled:
  - Architecture decision: "Embedding generation"
  - Modified files: `app/config.py`, `indexing/embeddings.py`, `indexing/chroma_store.py`, `evaluation/run_eval.py`
  - New file: `scripts/reindex.py`
  - Skills referenced: `embedding-generation.md`
  - Data model: Chroma collection name becomes `harmony_chunks_{model_name_slug}` — no SQLAlchemy schema change
  - Risk: dimension mismatch if old collection is queried with new model (high — handled by collection naming)

- [ ] `features/active/embedding-swap/03-implementation-plan.md` created and filled:
  - Step order: config → `embeddings.py` → `chroma_store.py` → `reindex.py` → `run_eval.py` guard → tests

## Files modified / created

### `app/config.py` or `settings.py`
```python
embedding_model: str = "all-mpnet-base-v2"
embedding_dim: int = 768
```
Both values present and not hardcoded elsewhere.

### `indexing/embeddings.py`
```python
_model = SentenceTransformer(settings.embedding_model)  # loaded once at module level

def embed_texts(texts: list[str], batch_size: int = 32) -> list[list[float]]:
    return _model.encode(texts, batch_size=batch_size).tolist()
```
- Model loaded once at import time, not inside `embed_texts()`
- Model name taken from `settings.embedding_model`

### `indexing/chroma_store.py`
```python
def _collection_name() -> str:
    slug = settings.embedding_model.replace("/", "_").replace("-", "_")
    return f"harmony_chunks_{slug}"
```
- Collection name derived from `settings.embedding_model`
- Old collection (`harmony_chunks_all_MiniLM_L6_v2`) not deleted — a `logger.warning()` emitted if it exists alongside the new one

### `scripts/reindex.py` (new file)
- Queries `DocumentRegistry` for all rows with `DocStatus.INDEXED`
- For each document: fetches existing chunks from DB (not re-parsing), calls `embed_texts()` with new model, upserts to new Chroma collection
- Preserves all existing metadata (patient_id, allowed_roles, entity_types, etc.)
- Accepts `--dry-run` flag that prints chunk counts without writing
- Idempotent: re-running does not create duplicate entries

### `evaluation/run_eval.py`
```python
collection_name = chroma_client.get_collection(settings.embedding_model...)
assert settings.embedding_model in collection_name.name, (
    f"Model/collection mismatch: configured '{settings.embedding_model}' "
    f"but collection is '{collection_name.name}'"
)
```
- Fails loudly (raises `AssertionError`) if model and collection do not match
- Guard runs before any retrieval eval assertions

## Conventions respected
- `embed_texts()` signature unchanged — all call sites unaffected
- Chroma upsert metadata schema unchanged — same required fields
- `BaseWorker` retry pattern unchanged in `EmbeddingWorker`

## Non-negotiables respected
- No external embedding API used — local `SentenceTransformer` only
- `allowed_roles` preserved in all re-indexed chunks
- `settings.embedding_model` not hardcoded anywhere outside config

## Tests expected
- Unit test: `embed_texts(["test"])` returns list of length `settings.embedding_dim` (768)
- Unit test: `_collection_name()` returns `"harmony_chunks_all_mpnet_base_v2"` for `settings.embedding_model = "all-mpnet-base-v2"`
- Unit test: `run_eval.py` guard raises `AssertionError` when model name does not appear in collection name
- Unit test: `reindex.py --dry-run` prints chunk counts without writing to Chroma
- Integration test: after `reindex.py` runs, `query_chunks(embed_texts(["metformin"])[0])` returns results from new collection

## What failing looks like
- Agent hardcodes `"all-mpnet-base-v2"` in `embeddings.py` instead of reading from settings
- Agent deletes the old Chroma collection in `chroma_store.py`
- Agent loads `SentenceTransformer` inside `embed_texts()` (called per document — catastrophic performance)
- Agent does not update collection name — dimension mismatch between 384-dim old collection and 768-dim new model
- Agent skips `reindex.py` and expects workers to re-embed on next ingest (existing documents would be missing from search)
- Agent omits eval guard — model/collection divergence goes undetected
