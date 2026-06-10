"""
Unit tests for POST /ingest/bulk and the _process_single_upload_bytes helper.

All external dependencies (S3, DB, audit logger) are mocked so these tests
run without AWS credentials or a live database.
"""
from __future__ import annotations

import io
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.main import app, _process_single_upload_bytes
import queues


# ---------------------------------------------------------------------------
# Byte fixtures
# ---------------------------------------------------------------------------

_PDF_BYTES = b"%PDF-1.4 fake content"
_TXT_BYTES = b"Patient notes: blood pressure normal."
_EXE_BYTES = b"MZfake executable content"


def _make_upload(name: str, data: bytes) -> tuple:
    return ("files", (name, io.BytesIO(data), "application/octet-stream"))


def _drain_queue() -> list[dict]:
    msgs = []
    while queues.parsing_queue.qsize() > 0:
        msg = queues.parsing_queue.get(timeout=0.1)
        if msg is not None:
            msgs.append(msg)
    return msgs


# ---------------------------------------------------------------------------
# Shared patches applied to every test
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _patch_s3():
    with patch("app.main.s3_upload", return_value=None), \
         patch("app.main.s3_upload_file", return_value=None):
        yield


@pytest.fixture(autouse=True)
def _patch_registry(monkeypatch):
    monkeypatch.setattr("app.main.register_document", lambda *a, **kw: MagicMock())
    monkeypatch.setattr("app.main.update_status", lambda *a, **kw: None)
    monkeypatch.setattr("app.main.is_duplicate_document", lambda filename: False)


@pytest.fixture(autouse=True)
def _patch_audit(monkeypatch):
    monkeypatch.setattr("app.main.log_event", lambda *a, **kw: None)


@pytest.fixture()
def client():
    return TestClient(app)


@pytest.fixture(autouse=True)
def _clear_queue():
    _drain_queue()
    yield
    _drain_queue()


# ---------------------------------------------------------------------------
# RBAC tests
# ---------------------------------------------------------------------------

class TestRbac:
    def test_billing_role_rejected_with_403(self, client):
        resp = client.post("/ingest/bulk", headers={"role": "billing"},
                           files=[_make_upload("scan.pdf", _PDF_BYTES)])
        assert resp.status_code == 403

    def test_radiologist_role_rejected_with_403(self, client):
        resp = client.post("/ingest/bulk", headers={"role": "radiologist"},
                           files=[_make_upload("scan.pdf", _PDF_BYTES)])
        assert resp.status_code == 403

    def test_doctor_role_accepted(self, client):
        resp = client.post("/ingest/bulk", headers={"role": "doctor"},
                           files=[_make_upload("scan.pdf", _PDF_BYTES)])
        assert resp.status_code == 200

    def test_nurse_role_accepted(self, client):
        resp = client.post("/ingest/bulk", headers={"role": "nurse"},
                           files=[_make_upload("note.txt", _TXT_BYTES)])
        assert resp.status_code == 200

    def test_admin_role_accepted(self, client):
        resp = client.post("/ingest/bulk", headers={"role": "admin"},
                           files=[_make_upload("note.txt", _TXT_BYTES)])
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Batch size limit
# ---------------------------------------------------------------------------

class TestBatchSizeLimit:
    def test_51_files_returns_422(self, client):
        files = [_make_upload(f"scan{i}.pdf", _PDF_BYTES) for i in range(51)]
        resp = client.post("/ingest/bulk", headers={"role": "doctor"}, files=files)
        assert resp.status_code == 422

    def test_50_files_accepted(self, client):
        files = [_make_upload(f"scan{i}.pdf", _PDF_BYTES) for i in range(50)]
        resp = client.post("/ingest/bulk", headers={"role": "doctor"}, files=files)
        assert resp.status_code == 200
        assert len(resp.json()["job_ids"]) == 50

    def test_1_file_accepted(self, client):
        resp = client.post("/ingest/bulk", headers={"role": "doctor"},
                           files=[_make_upload("scan.pdf", _PDF_BYTES)])
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Mixed-batch validation
# ---------------------------------------------------------------------------

class TestMixedBatch:
    def test_two_valid_and_one_exe_batch(self, client):
        files = [
            _make_upload("report1.pdf", _PDF_BYTES),
            _make_upload("notes.txt", _TXT_BYTES),
            _make_upload("malware.exe", _EXE_BYTES),
        ]
        resp = client.post("/ingest/bulk", headers={"role": "doctor"}, files=files)
        assert resp.status_code == 200
        job_ids = resp.json()["job_ids"]

        queued = [r for r in job_ids if r["status"] == "queued"]
        rejected = [r for r in job_ids if r["status"] == "rejected"]
        assert len(queued) == 2
        assert len(rejected) == 1
        assert rejected[0]["filename"] == "malware.exe"
        assert isinstance(rejected[0]["reason"], str)
        assert rejected[0]["doc_id"] is None

    def test_only_queued_files_reach_parsing_queue(self, client):
        files = [
            _make_upload("good.pdf", _PDF_BYTES),
            _make_upload("bad.exe", _EXE_BYTES),
        ]
        client.post("/ingest/bulk", headers={"role": "doctor"}, files=files)
        msgs = _drain_queue()
        assert len(msgs) == 1
        assert msgs[0]["original_filename"] == "good.pdf"

    def test_response_shape_for_rejected_file(self, client):
        resp = client.post("/ingest/bulk", headers={"role": "doctor"},
                           files=[_make_upload("bad.exe", _EXE_BYTES)])
        result = resp.json()["job_ids"][0]
        assert result["status"] == "rejected"
        assert result["doc_id"] is None
        assert isinstance(result["reason"], str)
        assert result["filename"] == "bad.exe"

    def test_response_shape_for_queued_file(self, client):
        resp = client.post("/ingest/bulk", headers={"role": "doctor"},
                           files=[_make_upload("scan.pdf", _PDF_BYTES)])
        result = resp.json()["job_ids"][0]
        assert result["status"] == "queued"
        assert isinstance(result["doc_id"], str)
        assert result["reason"] is None
        assert result["filename"] == "scan.pdf"


# ---------------------------------------------------------------------------
# Audit event
# ---------------------------------------------------------------------------

class TestAuditEvent:
    def test_bulk_ingest_submitted_event_emitted(self, client, monkeypatch):
        captured = []
        monkeypatch.setattr(
            "app.main.log_event",
            lambda event_type, **kw: captured.append({"event_type": event_type, **kw}),
        )
        files = [
            _make_upload("report1.pdf", _PDF_BYTES),
            _make_upload("notes.txt", _TXT_BYTES),
            _make_upload("bad.exe", _EXE_BYTES),
        ]
        client.post("/ingest/bulk", headers={"role": "doctor"}, files=files)
        batch_events = [e for e in captured if e["event_type"] == "BULK_INGEST_SUBMITTED"]
        assert len(batch_events) == 1

    def test_audit_event_has_counts_not_filenames(self, client, monkeypatch):
        captured = []
        monkeypatch.setattr(
            "app.main.log_event",
            lambda event_type, **kw: captured.append({"event_type": event_type, **kw}),
        )
        files = [
            _make_upload("scan.pdf", _PDF_BYTES),
            _make_upload("bad.exe", _EXE_BYTES),
        ]
        client.post("/ingest/bulk", headers={"role": "doctor"}, files=files)

        event = next(e for e in captured if e["event_type"] == "BULK_INGEST_SUBMITTED")
        details = event["details"]
        assert details["total"] == 2
        assert details["accepted"] == 1
        assert details["rejected"] == 1
        for key in details:
            assert "filename" not in key.lower()
        assert "patient" not in str(details).lower()

    def test_single_event_not_one_per_file(self, client, monkeypatch):
        captured_types = []
        monkeypatch.setattr(
            "app.main.log_event",
            lambda event_type, **kw: captured_types.append(event_type),
        )
        files = [_make_upload(f"scan{i}.pdf", _PDF_BYTES) for i in range(5)]
        client.post("/ingest/bulk", headers={"role": "doctor"}, files=files)
        assert captured_types.count("BULK_INGEST_SUBMITTED") == 1


# ---------------------------------------------------------------------------
# Exception isolation
# ---------------------------------------------------------------------------

class TestExceptionIsolation:
    def test_register_error_for_one_file_does_not_block_others(self, monkeypatch):
        call_count = 0

        def _register_side_effect(doc_id, filename, *args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 2:
                raise RuntimeError("DB unavailable for this file")
            return MagicMock()

        monkeypatch.setattr("app.main.register_document", _register_side_effect)
        monkeypatch.setattr("app.main.update_status", lambda *a, **kw: None)
        monkeypatch.setattr("app.main.is_duplicate_document", lambda f: False)

        result1 = _process_single_upload_bytes("ok1.pdf", _PDF_BYTES, "u1", "P001", "general")
        result2 = _process_single_upload_bytes("fail.pdf", _PDF_BYTES, "u1", "P001", "general")
        result3 = _process_single_upload_bytes("ok3.pdf", _PDF_BYTES, "u1", "P001", "general")

        assert result1["status"] == "queued"
        assert result2["status"] == "rejected"
        assert result2["reason"] is not None
        assert result3["status"] == "queued"

    def test_rejected_file_not_on_queue(self, monkeypatch):
        monkeypatch.setattr("app.main.is_duplicate_document", lambda f: False)
        _process_single_upload_bytes("bad.exe", _EXE_BYTES, "u1", "P001", "general")
        assert queues.parsing_queue.qsize() == 0

    def test_duplicate_file_rejected_not_enqueued(self, monkeypatch):
        monkeypatch.setattr("app.main.is_duplicate_document", lambda f: True)
        result = _process_single_upload_bytes("dup.pdf", _PDF_BYTES, "u1", "P001", "general")
        assert result["status"] == "rejected"
        assert result["reason"] == "Duplicate document"
        assert queues.parsing_queue.qsize() == 0


# ---------------------------------------------------------------------------
# DocumentValidator unit tests
# ---------------------------------------------------------------------------

class TestDocumentValidator:
    def test_pdf_accepted(self):
        from ingestion.validator import DocumentValidator
        v = DocumentValidator()
        ok, _ = v.validate("scan.pdf", _PDF_BYTES)
        assert ok

    def test_txt_accepted(self):
        from ingestion.validator import DocumentValidator
        v = DocumentValidator()
        ok, _ = v.validate("notes.txt", _TXT_BYTES)
        assert ok

    def test_exe_rejected_by_extension(self):
        from ingestion.validator import DocumentValidator
        v = DocumentValidator()
        ok, reason = v.validate("bad.exe", _EXE_BYTES)
        assert not ok
        assert "Unsupported file type" in reason

    def test_exe_magic_rejected_even_with_txt_extension(self):
        from ingestion.validator import DocumentValidator
        v = DocumentValidator()
        ok, reason = v.validate("sneaky.txt", _EXE_BYTES)
        assert not ok
        assert "Executable" in reason

    def test_empty_file_rejected(self):
        from ingestion.validator import DocumentValidator
        v = DocumentValidator()
        ok, reason = v.validate("empty.pdf", b"")
        assert not ok
        assert "empty" in reason.lower()

    def test_oversized_file_rejected(self, monkeypatch):
        from ingestion.validator import DocumentValidator
        from app import config as _cfg
        monkeypatch.setattr(_cfg.settings, "max_file_size_bytes", 10)
        v = DocumentValidator()
        ok, reason = v.validate("big.pdf", b"%PDF " + b"x" * 20)
        assert not ok
        assert "MB limit" in reason

    def test_unsupported_extension_rejected(self):
        from ingestion.validator import DocumentValidator
        v = DocumentValidator()
        ok, reason = v.validate("image.png", b"\x89PNG\r\n\x1a\n")
        assert not ok
        assert ".png" in reason
