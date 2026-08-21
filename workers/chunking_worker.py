"""
Chunking Worker
Downloads markdown from S3 → entity-preserving chunking → dedup via SHA256 →
passes chunks INLINE in queue message (no disk write) → pushes to pii_queue.

chunks.json is intentionally never written to disk: it contains plaintext PII
and exists only as a handoff to PiiWorker. Passing it inline in the message
eliminates the file entirely without losing any data.
"""
import logging
from workers.base_worker import BaseWorker
from ingestion.chunking.entity_preserving_chunker import chunk_markdown
from ingestion.registry import update_status, register_chunk
from ingestion.state_machine import DocStatus
from storage.s3_client import download_bytes
import queues

logger = logging.getLogger(__name__)


class ChunkingWorker(BaseWorker):
    def __init__(self):
        super().__init__("ChunkingWorker", queues.chunking_queue)

    def process(self, message: dict) -> None:
        doc_id = message["doc_id"]
        markdown_s3_key = message["markdown_s3_key"]

        markdown = download_bytes(markdown_s3_key).decode("utf-8")
        chunks = chunk_markdown(markdown, doc_id=doc_id)

        new_chunks = []
        duplicate_count = 0

        for chunk in chunks:
            is_new = register_chunk(
                chunk_id=chunk.chunk_id,
                doc_id=doc_id,
                chunk_hash=chunk.chunk_hash,
                chunk_index=chunk.chunk_index,
                section=chunk.section,
                page_number=chunk.page_number,
                parent_chunk_id=chunk.parent_chunk_id,
            )
            if is_new:
                new_chunks.append(chunk)
            else:
                duplicate_count += 1

        logger.info("Chunked %s: %d new, %d duplicates", doc_id, len(new_chunks), duplicate_count)

        update_status(doc_id, DocStatus.CHUNKED)

        if not new_chunks:
            update_status(doc_id, DocStatus.DUPLICATE)
            return

        # Serialize chunks inline — no file write, plaintext PII never touches disk
        serialised = [
            {
                "chunk_id": c.chunk_id,
                "text": c.text,
                "hash": c.chunk_hash,
                "chunk_index": c.chunk_index,
                "section": c.section,
                "page_number": c.page_number,
                "parent_chunk_id": c.parent_chunk_id,
                "entity_types": c.entity_types,
            }
            for c in new_chunks
        ]

        queues.pii_queue.put({
            **message,
            "chunks": serialised,
        })
