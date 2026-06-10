"""Streamlit page for bulk document ingestion (up to 50 files per batch)."""
from __future__ import annotations
import threading

import streamlit as st

from app.main import _process_single_upload_bytes
from app.dependencies import rate_limiter
from db.database import get_db
from db.models import DocumentRegistry
from ingestion.metadata.rbac_policy import get_ingest_allowed_roles
from ingestion.state_machine import DocStatus
from security.audit_logger import log_event
from security.auth import current_user

_MAX_FILES = 50

_workers_started = False
_worker_lock = threading.Lock()


def _ensure_workers() -> None:
    global _workers_started
    with _worker_lock:
        if not _workers_started:
            from workers.parser_worker import ParserWorker
            from workers.markdown_worker import MarkdownWorker
            from workers.chunking_worker import ChunkingWorker
            from workers.pii_worker import PiiWorker
            from workers.embedding_worker import EmbeddingWorker
            from workers.keyword_index_worker import KeywordIndexWorker

            for w in [ParserWorker(), MarkdownWorker(), ChunkingWorker(),
                      PiiWorker(), EmbeddingWorker(), KeywordIndexWorker()]:
                w.start()
            _workers_started = True


_STATUS_COLOR = {
    DocStatus.UPLOADED: "🔵",
    DocStatus.VALIDATED: "🟡",
    DocStatus.PARSING: "🟡",
    DocStatus.PARSED: "🟡",
    DocStatus.MARKDOWN_READY: "🟡",
    DocStatus.CHUNKED: "🟡",
    DocStatus.PII_PROCESSED: "🟡",
    DocStatus.EMBEDDED: "🟡",
    DocStatus.INDEXED: "🟢",
    DocStatus.FAILED: "🔴",
    DocStatus.DUPLICATE: "⚪",
}


def _recent_docs(limit: int = 30) -> list[DocumentRegistry]:
    with get_db() as db:
        return (
            db.query(DocumentRegistry)
            .order_by(DocumentRegistry.created_at.desc())
            .limit(limit)
            .all()
        )


def render() -> None:
    _ensure_workers()
    st.header("Bulk Upload — Medical Documents")

    user = current_user()
    if user is None or user["role"] not in get_ingest_allowed_roles():
        st.error(
            f"Access denied. Bulk upload requires one of: "
            f"{', '.join(sorted(get_ingest_allowed_roles()))}. "
            f"Your role: **{user['role'] if user else 'unauthenticated'}**"
        )
        return

    st.caption(
        f"Upload up to {_MAX_FILES} PDF, plain-text, or DICOM files at once. "
        "Each file is processed independently — one rejection does not block others."
    )

    col1, col2 = st.columns([2, 1])

    with col1:
        uploaded = st.file_uploader(
            "Choose files (max 50)",
            type=["pdf", "txt", "dcm"],
            accept_multiple_files=True,
            help="PDF, plain-text (.txt), or DICOM (.dcm) files. Max 50 MB per file.",
        )

    with col2:
        patient_id = st.text_input("Patient ID", value="UNKNOWN")
        department = st.selectbox(
            "Department",
            ["general", "cardiology", "oncology", "radiology", "billing"],
        )

    if uploaded and len(uploaded) > _MAX_FILES:
        st.error(f"Too many files selected ({len(uploaded)}). Maximum is {_MAX_FILES}.")
        return

    if st.button("Upload & Ingest Batch", type="primary", disabled=not uploaded):
        uploader_id = user["username"]

        if not rate_limiter.is_allowed(uploader_id):
            st.error(f"Rate limit exceeded for {uploader_id}. Max 10 uploads/minute.")
            return

        progress = st.progress(0, text="Processing batch…")
        results = []
        accepted = 0
        rejected = 0

        for i, f in enumerate(uploaded):
            content = f.read()
            result = _process_single_upload_bytes(
                filename=f.name,
                content=content,
                uploader_id=uploader_id,
                patient_id=patient_id,
                department=department,
            )
            results.append(result)
            if result["status"] == "queued":
                accepted += 1
            else:
                rejected += 1
            progress.progress((i + 1) / len(uploaded), text=f"Processed {i + 1}/{len(uploaded)} files…")

        log_event(
            "BULK_INGEST_SUBMITTED",
            user_id=uploader_id,
            details={"total": len(uploaded), "accepted": accepted, "rejected": rejected},
        )

        progress.empty()

        st.success(f"Batch complete — {accepted} queued, {rejected} rejected.")

        rows = []
        for r in results:
            if r["status"] == "queued":
                rows.append({
                    "Status": "✅ queued",
                    "File": r["filename"],
                    "Doc ID": (r["doc_id"] or "")[:12] + "…" if r["doc_id"] else "—",
                    "Reason": "—",
                })
            else:
                rows.append({
                    "Status": "❌ rejected",
                    "File": r["filename"],
                    "Doc ID": "—",
                    "Reason": r["reason"] or "—",
                })

        st.dataframe(rows, use_container_width=True, hide_index=True)

    st.markdown("---")
    st.subheader("Recent Documents")

    if st.button("Refresh"):
        st.rerun()

    docs = _recent_docs()
    if not docs:
        st.info("No documents ingested yet.")
        return

    rows = []
    for doc in docs:
        icon = _STATUS_COLOR.get(doc.status, "⚫")
        rows.append({
            "Status": f"{icon} {doc.status}",
            "File": doc.original_filename,
            "Doc ID": doc.doc_id[:12] + "…",
            "Type": doc.file_type or "—",
            "Retries": doc.retry_count,
            "Uploaded by": doc.uploader_id,
            "Created": doc.created_at.strftime("%Y-%m-%d %H:%M") if doc.created_at else "—",
        })

    st.dataframe(rows, use_container_width=True, hide_index=True)
