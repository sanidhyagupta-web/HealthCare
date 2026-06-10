from __future__ import annotations
import tempfile
import threading
from pathlib import Path

import streamlit as st

from app.dependencies import rate_limiter
from app.main import ingest_document
from db.database import init_db, get_db
from db.models import DocumentRegistry
from ingestion.state_machine import DocStatus

# Start pipeline workers once per process
_workers_started = False
_worker_lock = threading.Lock()


def _ensure_workers():
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


def _recent_docs(limit: int = 20) -> list[DocumentRegistry]:
    with get_db() as db:
        return (
            db.query(DocumentRegistry)
            .order_by(DocumentRegistry.created_at.desc())
            .limit(limit)
            .all()
        )


def render():
    _ensure_workers()
    st.header("Upload Medical Documents")

    col1, col2 = st.columns([2, 1])

    with col1:
        uploaded = st.file_uploader(
            "Choose file(s)",
            type=["pdf", "txt"],
            accept_multiple_files=True,
            help="Typed PDFs, scanned PDFs, or plain text clinical notes.",
        )

    with col2:
        uploader_id = st.text_input("Your user ID", value="doctor_01")
        patient_id = st.text_input("Patient ID", value="P0001")
        department = st.selectbox(
            "Department",
            ["general", "cardiology", "oncology", "radiology", "billing"],
        )

    if st.button("Upload & Ingest", type="primary", disabled=not uploaded):
        if not rate_limiter.is_allowed(uploader_id):
            st.error(f"Rate limit exceeded for {uploader_id}. Max 10 uploads/minute.")
            return

        progress = st.progress(0, text="Ingesting documents...")
        success, failed = [], []

        for i, f in enumerate(uploaded):
            with tempfile.NamedTemporaryFile(delete=False, suffix=Path(f.name).suffix) as tmp:
                tmp.write(f.read())
                tmp_path = tmp.name

            try:
                doc_id = ingest_document(
                    tmp_path,
                    uploader_id=uploader_id,
                    patient_id=patient_id,
                    department=department,
                )
                success.append((f.name, doc_id))
            except ValueError as e:
                failed.append((f.name, str(e)))

            progress.progress((i + 1) / len(uploaded))

        progress.empty()

        if success:
            st.success(f"Queued {len(success)} document(s) for processing.")
            for name, doc_id in success:
                st.caption(f"✓ {name} → `{doc_id[:8]}…`")
        if failed:
            for name, reason in failed:
                st.error(f"✗ {name}: {reason}")

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
