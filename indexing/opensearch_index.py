"""
BM25 keyword index using rank-bm25.
Serves as the local stand-in for OpenSearch keyword search.
Index is in-memory but persisted to disk as JSON after each upsert.
"""
from __future__ import annotations
import json
import logging
from pathlib import Path
from app.config import settings

logger = logging.getLogger(__name__)

_INDEX_FILE = settings.data_dir / "bm25_index.json"

# In-memory corpus: list of {chunk_id, text, metadata}
_corpus: list[dict] = []
_bm25 = None


def _rebuild_bm25():
    global _bm25
    if not _corpus:
        _bm25 = None
        return
    try:
        from rank_bm25 import BM25Okapi
        tokenised = [doc["text"].lower().split() for doc in _corpus]
        _bm25 = BM25Okapi(tokenised)
    except ImportError:
        logger.warning("rank-bm25 not installed; keyword search disabled. pip install rank-bm25")
        _bm25 = None


def _save():
    _INDEX_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(_INDEX_FILE, "w") as f:
        json.dump(_corpus, f)


def _load():
    global _corpus
    if _INDEX_FILE.exists():
        with open(_INDEX_FILE) as f:
            _corpus = json.load(f)
        _rebuild_bm25()
        logger.info("Loaded BM25 index: %d documents", len(_corpus))


def index_chunk(chunk_id: str, text: str, metadata: dict) -> None:
    global _corpus
    # Remove existing entry if present (upsert behaviour)
    _corpus = [c for c in _corpus if c["chunk_id"] != chunk_id]
    _corpus.append({"chunk_id": chunk_id, "text": text, "metadata": metadata})
    _rebuild_bm25()
    _save()


def keyword_search(query: str, n_results: int = 5) -> list[dict]:
    if not _bm25 or not _corpus:
        _load()
    if not _bm25:
        return []

    tokens = query.lower().split()
    scores = _bm25.get_scores(tokens)
    ranked = sorted(enumerate(scores), key=lambda x: x[1], reverse=True)

    results = []
    for idx, score in ranked[:n_results]:
        if score > 0:
            entry = _corpus[idx]
            results.append({
                "chunk_id": entry["chunk_id"],
                "text": entry["text"],
                "metadata": entry["metadata"],
                "score": float(score),
            })
    return results


def keyword_search_filtered(
    query: str,
    n_results: int = 5,
    chunk_id_filter: set[str] | None = None,
) -> list[dict]:
    """
    Like keyword_search but restricts scoring to chunks in chunk_id_filter.
    Used for PII-based metadata pre-filtering (Top-D selection).
    """
    if not _bm25 or not _corpus:
        _load()
    if not _bm25:
        return []

    tokens = query.lower().split()
    scores = _bm25.get_scores(tokens)

    results = []
    for idx, score in enumerate(scores):
        if score <= 0:
            continue
        entry = _corpus[idx]
        if chunk_id_filter is not None and entry["chunk_id"] not in chunk_id_filter:
            continue
        results.append({
            "chunk_id": entry["chunk_id"],
            "text": entry["text"],
            "metadata": entry["metadata"],
            "score": float(score),
        })

    results.sort(key=lambda x: x["score"], reverse=True)
    return results[:n_results]


# Load on module import
_load()
