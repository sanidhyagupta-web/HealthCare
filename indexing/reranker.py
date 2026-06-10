"""
Cross-encoder re-ranker.
Takes a shortlist of RRF-merged candidates and re-scores each (query, chunk) pair
using a cross-encoder model for higher-precision ranking.
"""
from __future__ import annotations
import logging

logger = logging.getLogger(__name__)

_MODEL_NAME = "cross-encoder/ms-marco-MiniLM-L-6-v2"
_model = None


def _get_model():
    global _model
    if _model is None:
        from sentence_transformers import CrossEncoder
        logger.info("Loading cross-encoder model: %s", _MODEL_NAME)
        _model = CrossEncoder(_MODEL_NAME, max_length=512)
        logger.info("Cross-encoder ready")
    return _model


def rerank(query: str, candidates: list[dict], top_k: int) -> list[dict]:
    """
    Re-rank candidates using a cross-encoder.

    Args:
        query: the user's search query
        candidates: list of result dicts with at least a 'text' key
        top_k: number of results to return after re-ranking

    Returns:
        top_k results sorted by cross-encoder score descending
    """
    if not candidates:
        return []

    model = _get_model()
    pairs = [(query, c["text"]) for c in candidates]
    scores = model.predict(pairs)

    for candidate, score in zip(candidates, scores):
        candidate["rerank_score"] = round(float(score), 4)

    reranked = sorted(candidates, key=lambda c: c["rerank_score"], reverse=True)
    return reranked[:top_k]
