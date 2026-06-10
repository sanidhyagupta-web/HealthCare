"""Generate vector embeddings using sentence-transformers."""
from __future__ import annotations
import logging
from app.config import settings

logger = logging.getLogger(__name__)

_model = None


def _get_model():
    global _model
    if _model is None:
        try:
            from sentence_transformers import SentenceTransformer
            logger.info("Loading embedding model: %s", settings.embedding_model)
            _model = SentenceTransformer(settings.embedding_model)
        except ImportError:
            raise RuntimeError(
                "sentence-transformers not installed. Run: pip install sentence-transformers"
            )
    return _model


def embed_texts(texts: list[str]) -> list[list[float]]:
    model = _get_model()
    embeddings = model.encode(
        texts,
        batch_size=settings.embedding_batch_size,
        show_progress_bar=False,
        convert_to_numpy=True,
    )
    return embeddings.tolist()


def embed_query(query: str) -> list[float]:
    return embed_texts([query])[0]
