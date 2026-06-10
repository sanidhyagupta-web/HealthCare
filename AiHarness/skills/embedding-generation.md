# Skill: Embedding Generation

## What this covers
Generating and storing embeddings for redacted chunks in this repo.

## Model
`all-MiniLM-L6-v2` (SentenceTransformer, 384-dim). Configured in `app/config.py` as `settings.embedding_model`. Do not use OpenAI, Cohere, or any external embedding API — the project runs locally.

## Entry point
`workers/embedding_worker.py` reads from `queues.embedding_queue`. After PiiWorker, redacted chunks arrive here.

## Embedding function
`indexing/embeddings.py` — call `embed_texts(texts: list[str], batch_size: int) -> list[list[float]]`.

```python
# Good
from indexing.embeddings import embed_texts
from app.config import settings

embeddings = embed_texts(texts, batch_size=settings.embedding_batch_size)  # default 32
```

## Chroma upsert
`indexing/chroma_store.py` — call `upsert_chunks(chunks, embeddings)`. Each document in Chroma must include all required metadata fields.

```python
# Good — full metadata required
chroma_store.upsert_chunks([
    {
        "chunk_id": chunk["chunk_id"],
        "text": chunk["text"],          # redacted text
        "embedding": embedding,
        "metadata": {
            "patient_id": chunk["patient_id"],
            "doc_id": chunk["doc_id"],
            "source_file": chunk["source_file"],
            "source_page": chunk["page_number"],
            "source_section": chunk["section"],
            "allowed_roles": chunk["allowed_roles"],
            "chunk_index": chunk["chunk_index"],
            "entity_types": chunk["entity_types"],
        }
    }
    for chunk, embedding in zip(chunks, embeddings)
])
```

## Status updates
After successful upsert, call `update_status(doc_id, DocStatus.EMBEDDED)`. After both EmbeddingWorker and KeywordIndexWorker complete, the final status is `INDEXED` — EmbeddingWorker sets `EMBEDDED`, KeywordIndexWorker sets `INDEXED`.

## Retry behavior
EmbeddingWorker extends BaseWorker. On embedding failure (model load error, OOM), the message is retried up to `settings.max_retries`. Do not catch `Exception` and continue.

## Bad examples

```python
# BAD: using OpenAI
import openai
embedding = openai.Embedding.create(input=text, model="text-embedding-ada-002")

# BAD: embedding raw (unredacted) chunks
embeddings = embed_texts([c["raw_text"] for c in chunks])

# BAD: upsert without allowed_roles in metadata
collection.add(documents=[text], embeddings=[emb], ids=[chunk_id])
# Missing allowed_roles breaks RBAC filtering at query time
```

## Failure modes seen
- Agent embeds raw chunk text before PII redaction — `[PATIENT_NAME]` replacements don't exist yet.
- Agent omits `allowed_roles` from Chroma metadata — access control filter silently passes everything.
- Agent creates a new SentenceTransformer instance per chunk instead of per worker — huge performance hit.

## Must NOT do
- Embed text that hasn't gone through PiiWorker.
- Omit `allowed_roles` from Chroma metadata.
- Use an external embedding API.
- Load the SentenceTransformer model inside `process()` — load once in `__init__`.
