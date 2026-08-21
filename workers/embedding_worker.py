"""
Embedding Worker
Reads redacted chunks → generates embeddings → stores in Chroma.
"""
from __future__ import annotations
import json
import logging
from workers.base_worker import BaseWorker
from indexing.embeddings import embed_texts
from indexing.chroma_store import upsert_chunks
from ingestion.registry import update_status
from ingestion.state_machine import DocStatus
import queues

logger = logging.getLogger(__name__)


class EmbeddingWorker(BaseWorker):
    def __init__(self):
        super().__init__("EmbeddingWorker", queues.embedding_queue)

    def process(self, message: dict) -> None:
        doc_id = message["doc_id"]
        redacted_path = message["redacted_path"]

        chunks = json.loads(open(redacted_path, encoding="utf-8").read())
        if not chunks:
            logger.warning("No chunks to embed for %s", doc_id)
            update_status(doc_id, DocStatus.EMBEDDED)
            return

        texts = [c["text"] for c in chunks]
        embeddings = embed_texts(texts)

        upsert_chunks(
            chunk_ids=[c["chunk_id"] for c in chunks],
            embeddings=embeddings,
            documents=texts,
            metadatas=[c["metadata"] for c in chunks],
        )

        update_status(doc_id, DocStatus.EMBEDDED)
        update_status(doc_id, DocStatus.INDEXED)
        logger.info("Embedded and indexed %d chunks for doc %s", len(chunks), doc_id)
