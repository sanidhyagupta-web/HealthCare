"""
Entry point for the ingestion pipeline.

Provides:
- ``ingest_document()``  — Python API used by the Streamlit single-file UI.
- ``POST /ingest/bulk`` — FastAPI endpoint for batch uploads (up to 50 files).
"""
from __future__ import annotations
import uuid
import shutil
import logging
from pathlib import Path
from botocore.exceptions import BotoCoreError, ClientError, NoCredentialsError, TokenRetrievalError

from fastapi import FastAPI, File, Header, HTTPException, UploadFile

from db.database import init_db
from ingestion.registry import register_document, update_status, is_duplicate_document
from ingestion.validator import validate_file, DocumentValidator
from ingestion.state_machine import DocStatus
from ingestion.metadata.rbac_policy import get_ingest_allowed_roles
from security.audit_logger import log_event
from app.config import settings
from storage.s3_client import upload as s3_upload, upload_file as s3_upload_file
import queues

logger = logging.getLogger(__name__)

app = FastAPI(title="Healthcare Ingestion API")
_validator = DocumentValidator()


# ---------------------------------------------------------------------------
# Single-file Python API (used by Streamlit upload_page.py)
# ---------------------------------------------------------------------------

def ingest_document(
    file_path: str | Path,
    uploader_id: str = "anonymous",
    patient_id: str = "UNKNOWN",
    department: str = "general",
) -> str:
    """
    Validate and enqueue a document for ingestion.
    Returns the assigned doc_id.
    Raises ValueError on validation failure.
    """
    path = Path(file_path)
    is_valid, reason = validate_file(path)

    if not is_valid:
        log_event("VALIDATION_FAILED", user_id=uploader_id, details={"reason": reason, "file": str(path)})
        dest = settings.failed_dir / "validation" / path.name
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, dest)
        raise ValueError(f"Validation failed: {reason}")

    doc_id = str(uuid.uuid4())
    suffix = path.suffix.lower()

    # Upload raw file to S3 with KMS encryption — never touches local disk after this
    raw_s3_key = f"raw/{doc_id}/{path.name}"
    try:
        s3_upload_file(raw_s3_key, path)
    except (TokenRetrievalError, NoCredentialsError) as exc:
        raise ValueError(
            "AWS credentials are unavailable or expired. "
            "Run `aws sso login --profile KDU-Developer-743298171118` and try again."
        ) from exc
    except (ClientError, BotoCoreError) as exc:
        raise ValueError(f"S3 upload failed: {exc}") from exc

    register_document(doc_id, path.name, f"s3://{settings.s3_bucket}/{raw_s3_key}", uploader_id=uploader_id)
    update_status(doc_id, DocStatus.VALIDATED)

    queues.parsing_queue.put({
        "doc_id": doc_id,
        "raw_s3_key": raw_s3_key,
        "file_suffix": suffix,
        "original_filename": path.name,
        "uploader_id": uploader_id,
        "patient_id": patient_id,
        "department": department,
        "retry_count": 0,
    })

    log_event("DOCUMENT_INGESTED", user_id=uploader_id, doc_id=doc_id,
              details={"filename": path.name, "department": department, "s3_key": raw_s3_key})
    logger.info("Document %s uploaded to S3 and enqueued", doc_id)
    return doc_id


# ---------------------------------------------------------------------------
# Bulk ingest helper (shared by HTTP endpoint and Streamlit bulk UI)
# ---------------------------------------------------------------------------

def _process_single_upload_bytes(
    filename: str,
    content: bytes,
    uploader_id: str,
    patient_id: str,
    department: str,
) -> dict:
    """
    Validate, encrypt-upload, register, and enqueue one file.

    Returns {"doc_id": str|None, "filename": str, "status": "queued"|"rejected", "reason": str|None}.
    Never raises — all exceptions are surfaced as a rejected entry so one file's
    failure cannot block the rest of the batch.
    """
    try:
        is_valid, reason = _validator.validate(filename, content)
        if not is_valid:
            return {"doc_id": None, "filename": filename, "status": "rejected", "reason": reason}

        if is_duplicate_document(filename):
            return {"doc_id": None, "filename": filename, "status": "rejected", "reason": "Duplicate document"}

        doc_id = str(uuid.uuid4())
        suffix = Path(filename).suffix.lower()
        raw_s3_key = f"raw/{doc_id}/{filename}"

        s3_upload(raw_s3_key, content)

        register_document(
            doc_id, filename,
            f"s3://{settings.s3_bucket}/{raw_s3_key}",
            uploader_id=uploader_id,
        )
        update_status(doc_id, DocStatus.VALIDATED)

        queues.parsing_queue.put({
            "doc_id": doc_id,
            "raw_s3_key": raw_s3_key,
            "file_suffix": suffix,
            "original_filename": filename,
            "uploader_id": uploader_id,
            "patient_id": patient_id,
            "department": department,
            "retry_count": 0,
        })

        return {"doc_id": doc_id, "filename": filename, "status": "queued", "reason": None}

    except Exception as exc:
        logger.error("Bulk ingest: error processing %s: %s", filename, exc)
        return {"doc_id": None, "filename": filename, "status": "rejected", "reason": str(exc)}


# ---------------------------------------------------------------------------
# POST /ingest/bulk — HTTP endpoint
# ---------------------------------------------------------------------------

@app.post("/ingest/bulk")
async def bulk_ingest(
    role: str = Header(...),
    files: list[UploadFile] = File(...),
    uploader_id: str = Header(default="anonymous"),
    patient_id: str = Header(default="UNKNOWN"),
    department: str = Header(default="general"),
) -> dict:
    """
    Accept up to 50 files in one multipart request.

    Returns immediately with per-file queued/rejected status.
    Exactly one BULK_INGEST_SUBMITTED audit event is emitted for the batch.
    """
    if role not in get_ingest_allowed_roles():
        raise HTTPException(status_code=403, detail="Insufficient role for bulk ingest")

    if len(files) > 50:
        raise HTTPException(status_code=422, detail="Maximum 50 files per batch")

    results = []
    accepted = 0
    rejected = 0

    for file in files:
        content = await file.read()
        filename = file.filename or "unknown"
        result = _process_single_upload_bytes(filename, content, uploader_id, patient_id, department)
        results.append(result)
        if result["status"] == "queued":
            accepted += 1
        else:
            rejected += 1

    log_event(
        "BULK_INGEST_SUBMITTED",
        user_id=uploader_id,
        details={"total": len(files), "accepted": accepted, "rejected": rejected},
    )

    return {"job_ids": results}
