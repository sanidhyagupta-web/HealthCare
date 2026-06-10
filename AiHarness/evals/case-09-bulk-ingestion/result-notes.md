# Eval Case 09 — Result Notes

Evaluated against `expected.md` on 2026-05-25.

## Scoring

| Criterion | Weight | Result | Notes |
|-----------|--------|--------|-------|
| Templates created and filled | 20% | **PASS** | All three spec files created in `features/active/bulk-ingestion/` with correct content |
| Correct skills referenced | 20% | **PASS** | `document-ingestion.md`, `audit-logging.md`, `access-control.md` read before implementation |
| Implementation plan followed in order | 20% | **PASS** | Pre-work → config → core logic → security → queue → tests → docs |
| Non-negotiables respected | 20% | **PASS** | No filenames in audit event; rejected files never enqueued; roles from `rbac_policy.py`; no hardcoded strings |
| Code style matches existing repo | 20% | **PASS** | `from __future__ import annotations`, `logger = logging.getLogger(__name__)`, same queue message shape |
| **Total** | 100% | **100% — PASS** | |

---

## What the agent did

1. Read `Agents.md`, the existing skills, templates, and all relevant source files before writing any code.
2. Created `features/active/bulk-ingestion/` with all three spec files filled correctly.
3. Added `_INGEST_ALLOWED_ROLES` and `get_ingest_allowed_roles()` to `ingestion/metadata/rbac_policy.py` — no role strings hardcoded elsewhere.
4. Also added missing `radiology` and `oncology` departments to `rbac_policy.py` (they were referenced in the Streamlit UI dropdown but would have caused `ValueError` in PiiWorker).
5. Added `SUPPORTED_EXTENSIONS`, `DocumentValidator` class (works on in-memory bytes, not file paths), and DICOM magic-byte validation to `ingestion/validator.py`.
6. Added `is_duplicate_document(filename)` to `ingestion/registry.py` — filename-based duplicate guard with no schema changes.
7. Added FastAPI `app` instance, `_process_single_upload_bytes()` helper, and `POST /ingest/bulk` to `app/main.py`. Existing `ingest_document()` left untouched. S3 imports moved to module level to enable test patching.
8. Created `ui/bulk_upload_page.py` — Streamlit bulk upload page with RBAC gate, per-file result table, progress bar, and single `BULK_INGEST_SUBMITTED` audit event mirroring the HTTP endpoint.
9. Added "Bulk Upload" nav item to `ui/streamlit_app.py`.
10. Wrote 25 unit tests in `tests/unit/test_bulk_ingestion.py` — all pass (0.29 s).
11. Added `fastapi`, `python-multipart`, `uvicorn` to `requirements.txt` and installed them.

---

## Divergences from expected.md

| Expected | Actual | Assessment |
|---|---|---|
| Helper named `_process_single_upload(file: UploadFile)` | Named `_process_single_upload_bytes(filename, content, ...)` taking raw bytes | **Intentional improvement.** Decouples helper from FastAPI types; the HTTP endpoint reads bytes then calls the helper; Streamlit UI calls the same helper directly without HTTP overhead. Logical structure identical. |
| `get_role(role)` from `rbac_policy.py` for role validation | `get_ingest_allowed_roles()` from `rbac_policy.py` used as `role not in get_ingest_allowed_roles()` | **Equivalent.** No hardcoded role strings; `rbac_policy.py` is the single source. `get_role()` was described as a validator function — `get_ingest_allowed_roles()` is clearer about intent. |
| Integration test: 3-file batch → all reach `DocStatus.INDEXED` | Not implemented | **Expected gap.** Requires live S3 + running workers. Noted in implementation plan as `pytest -m integration`. |

---

## Failures from "What failing looks like" — none triggered

| Failure mode | Triggered? |
|---|---|
| Awaits ingestion before returning | No — response returned immediately after `parsing_queue.put()` |
| One `DOC_VALIDATED` per file instead of one batch event | No — single `BULK_INGEST_SUBMITTED` emitted once after the loop |
| Single file exception blocks remaining files | No — all exceptions caught inside `_process_single_upload_bytes`; loop continues |
| Hardcoded `["doctor","nurse","admin"]` inline | No — `get_ingest_allowed_roles()` from `rbac_policy.py` |
| New `bulk_queue` created | No — `queues.parsing_queue` used directly |
| Filenames in audit event | No — details contain only `{total, accepted, rejected}` |

---

## Skill sharpening needed

None. All patterns followed the existing skills without invention:
- `document-ingestion.md`: validate → S3 upload → register → enqueue pattern followed exactly.
- `audit-logging.md`: single event per batch, aggregate counts only, no PHI in details.
- `access-control.md`: role check from `rbac_policy.py`; 403 for disallowed roles.
