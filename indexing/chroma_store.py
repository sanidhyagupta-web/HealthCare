"""ChromaDB vector store interface."""
from __future__ import annotations
import logging
from app.config import settings

logger = logging.getLogger(__name__)

_client = None
_collection = None


def _get_collection():
    global _client, _collection
    if _collection is None:
        try:
            import chromadb
            from chromadb.config import Settings as ChromaSettings

            _client = chromadb.PersistentClient(
                path=str(settings.chroma_dir),
            )
            _collection = _client.get_or_create_collection(
                name=settings.chroma_collection_name,
                metadata={"hnsw:space": "cosine"},
            )
            logger.info("Chroma collection ready: %s", settings.chroma_collection_name)
        except ImportError:
            raise RuntimeError("chromadb not installed. Run: pip install chromadb")
    return _collection


def upsert_chunks(
    chunk_ids: list[str],
    embeddings: list[list[float]],
    documents: list[str],
    metadatas: list[dict],
) -> None:
    col = _get_collection()
    # Chroma requires metadata values to be str/int/float/bool
    safe_metadatas = [_sanitise_metadata(m) for m in metadatas]
    col.upsert(
        ids=chunk_ids,
        embeddings=embeddings,
        documents=documents,
        metadatas=safe_metadatas,
    )
    logger.info("Upserted %d chunks to Chroma", len(chunk_ids))


def query(
    query_embedding: list[float],
    n_results: int = 5,
    where: dict | None = None,
) -> list[dict]:
    col = _get_collection()
    kwargs = dict(
        query_embeddings=[query_embedding],
        n_results=n_results,
        include=["documents", "metadatas", "distances"],
    )
    if where:
        kwargs["where"] = where

    results = col.query(**kwargs)
    output = []
    for i, doc_id in enumerate(results["ids"][0]):
        output.append({
            "chunk_id": doc_id,
            "text": results["documents"][0][i],
            "metadata": results["metadatas"][0][i],
            "score": 1 - results["distances"][0][i],  # cosine similarity
        })
    return output


def _sanitise_metadata(meta: dict) -> dict:
    safe = {}
    for k, v in meta.items():
        if isinstance(v, (str, int, float, bool)):
            safe[k] = v
        elif isinstance(v, list):
            safe[k] = ",".join(str(x) for x in v)
        elif v is None:
            safe[k] = ""
        else:
            safe[k] = str(v)
    return safe
