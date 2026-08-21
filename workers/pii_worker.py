"""
PII Worker
Detects PII → encrypts PHI → redacts text → adds metadata + RBAC → pushes to embedding + keyword queues.
Chunks arrive inline in the queue message (no file read) — plaintext PII never touches local disk.
"""
import json
import logging
from workers.base_worker import BaseWorker
from ingestion.pii.pii_detector import detect_pii
from ingestion.pii.pii_redactor import redact_text
from ingestion.metadata.metadata_builder import build_chunk_metadata
from ingestion.registry import update_status, mark_chunk_redacted
from ingestion.state_machine import DocStatus
from security.encryption import encrypt
from security.audit_logger import log_event
from indexing.pii_entity_index import register_entities
from app.config import settings
import queues

logger = logging.getLogger(__name__)


class PiiWorker(BaseWorker):
    def __init__(self):
        super().__init__("PiiWorker", queues.pii_queue)

    def process(self, message: dict) -> None:
        doc_id = message["doc_id"]
        patient_id = message.get("patient_id", "UNKNOWN")
        department = message.get("department", "general")
        source_file = message.get("original_filename", doc_id)
        uploader_id = message.get("uploader_id", "system")

        # Chunks arrive inline — no file read needed
        chunks = message["chunks"]
        redacted_chunks = []

        for chunk in chunks:
            text = chunk["text"]
            entities = detect_pii(text)

            # Register entity hashes BEFORE encrypting (index stores only hashes)
            # Pass doc_id so PERSON/PATIENT_NAME hits expand to the full document
            if entities:
                register_entities(chunk["chunk_id"], doc_id, entities)

            # Encrypt raw PHI values for secure storage
            encrypted_entities = []
            for e in entities:
                encrypted_entities.append({
                    "entity_type": e.entity_type,
                    "encrypted_value": encrypt(e.text),
                    "start": e.start,
                    "end": e.end,
                    "score": e.score,
                })

            redacted = redact_text(text, entities)
            mark_chunk_redacted(chunk["chunk_id"])

            from ingestion.metadata.rbac_policy import get_allowed_roles
            metadata = {
                "patient_id": patient_id,
                "doc_id": doc_id,
                "chunk_id": chunk["chunk_id"],
                "source_file": source_file,
                "source_page": chunk.get("page_number", 0),
                "source_section": chunk.get("section", ""),
                "chunk_index": chunk.get("chunk_index", 0),
                "parent_chunk_id": chunk.get("parent_chunk_id") or "",
                "department": department,
                "allowed_roles": get_allowed_roles(department),
            }

            redacted_chunks.append({
                "chunk_id": chunk["chunk_id"],
                "doc_id": doc_id,
                "text": redacted,
                "hash": chunk["hash"],
                "pii_entities": encrypted_entities,
                "metadata": metadata,
            })

        # Persist redacted chunks
        redacted_dir = settings.processed_dir / "redacted" / doc_id
        redacted_dir.mkdir(parents=True, exist_ok=True)
        redacted_path = redacted_dir / "redacted_chunks.json"
        redacted_path.write_text(json.dumps(redacted_chunks, indent=2), encoding="utf-8")

        update_status(doc_id, DocStatus.PII_PROCESSED)
        log_event("PII_PROCESSED", user_id=uploader_id, doc_id=doc_id,
                  details={"chunk_count": len(redacted_chunks)})

        payload = {**message, "redacted_path": str(redacted_path)}
        queues.extraction_queue.put(payload)
