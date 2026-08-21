from __future__ import annotations
import logging
from datetime import datetime
from typing import Optional
from db.database import get_db
from db.models import DocumentRegistry, ChunkRegistry
from ingestion.state_machine import DocStatus, can_transition

logger = logging.getLogger(__name__)


class RegistryError(Exception):
    pass


def register_document(
    doc_id: str,
    filename: str,
    raw_path: str,
    uploader_id: str = "anonymous",
) -> DocumentRegistry:
    with get_db() as db:
        entry = DocumentRegistry(
            doc_id=doc_id,
            original_filename=filename,
            raw_path=raw_path,
            status=DocStatus.UPLOADED,
            uploader_id=uploader_id,
        )
        db.add(entry)
    logger.info("Registered doc %s with status UPLOADED", doc_id)
    return entry


def update_status(
    doc_id: str,
    new_status: DocStatus,
    error_message: Optional[str] = None,
    metadata_update: Optional[dict] = None,
    file_type: Optional[str] = None,
) -> None:
    with get_db() as db:
        entry = db.query(DocumentRegistry).filter_by(doc_id=doc_id).first()
        if not entry:
            raise RegistryError(f"Document {doc_id} not found")

        current = DocStatus(entry.status)
        if not can_transition(current, new_status):
            raise RegistryError(
                f"Invalid transition {current} -> {new_status} for {doc_id}"
            )

        entry.status = new_status
        entry.updated_at = datetime.utcnow()

        if error_message:
            entry.error_message = error_message
        if file_type:
            entry.file_type = file_type
        if metadata_update:
            existing = entry.doc_metadata or {}
            existing.update(metadata_update)
            entry.doc_metadata = existing
        if new_status == DocStatus.FAILED:
            entry.retry_count = (entry.retry_count or 0) + 1

    logger.info("Updated doc %s -> %s", doc_id, new_status)


def is_duplicate_document(filename: str) -> bool:
    """Return True if a non-failed, non-duplicate document with this filename exists."""
    terminal_statuses = {DocStatus.FAILED, DocStatus.DUPLICATE}
    with get_db() as db:
        existing = (
            db.query(DocumentRegistry)
            .filter(
                DocumentRegistry.original_filename == filename,
                DocumentRegistry.status.notin_([s.value for s in terminal_statuses]),
            )
            .first()
        )
        return existing is not None


def get_document(doc_id: str) -> Optional[DocumentRegistry]:
    with get_db() as db:
        return db.query(DocumentRegistry).filter_by(doc_id=doc_id).first()


def register_chunk(
    chunk_id: str,
    doc_id: str,
    chunk_hash: str,
    chunk_index: int,
    section: str,
    page_number: int,
    parent_chunk_id: Optional[str] = None,
) -> bool:
    """Returns True if chunk is new, False if duplicate."""
    with get_db() as db:
        existing = db.query(ChunkRegistry).filter_by(chunk_hash=chunk_hash).first()
        if existing:
            return False
        entry = ChunkRegistry(
            chunk_id=chunk_id,
            doc_id=doc_id,
            chunk_hash=chunk_hash,
            chunk_index=chunk_index,
            section=section,
            page_number=page_number,
            parent_chunk_id=parent_chunk_id,
        )
        db.add(entry)
    return True


def mark_chunk_redacted(chunk_id: str) -> None:
    with get_db() as db:
        entry = db.query(ChunkRegistry).filter_by(chunk_id=chunk_id).first()
        if entry:
            entry.is_redacted = 1
