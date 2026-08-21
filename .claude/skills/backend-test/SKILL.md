---
name: backend-test
description: Write backend tests using a two-tier strategy — service tests for business logic, integration tests for API/DB contracts.
---

# Write Backend Tests

Write tests for the Python backend (`app/`, `ingestion/`, `security/`, `search/`, `llm/`, `db/`, etc.) using pytest. This repo has no Testcontainers/real-DB tier — everything runs fast, in-process, with I/O boundaries (S3, the SQLite registry, the audit logger) mocked via `unittest.mock`/`monkeypatch`. See `tests/unit/test_bulk_ingestion.py` and `tests/unit/test_researcher_role.py` for the two patterns below.

## Two-Tier Strategy

### Tier 1 — Pure Service Tests (fast, numerous)

Test business logic (RBAC filtering, PII masking, validators) as plain function calls — no mocking needed when the function itself has no I/O. Cover every role/department combination, every masking rule, every validation branch.

**When to write:** Every acceptance-criteria scenario, every business-logic branch, every validation rule, every error case.

```python
# tests/unit/test_researcher_role.py — real pattern from this repo
import pytest
from ingestion.pii.role_based_masking import apply_role_mask, RESEARCHER_MASKED_ENTITIES
from security.access_control import filter_results_by_role


@pytest.fixture
def chunk_with_patient_name():
    return {
        "text": "Patient [PATIENT_NAME] was admitted with chest pain.",
        "entity_types": ["PATIENT_NAME"],
        "metadata": {"chunk_id": "c1", "allowed_roles": ["doctor", "nurse", "researcher"]},
    }


def test_researcher_cannot_see_patient_name(chunk_with_patient_name):
    result = apply_role_mask(chunk_with_patient_name, "researcher")
    assert "[PATIENT_NAME]" not in result["text"]


def test_researcher_blocked_from_billing(chunk_billing_department):
    results = filter_results_by_role([chunk_billing_department], "researcher")
    assert len(results) == 0
```

**Patterns:**
- Fixtures build fixture dicts (chunk/metadata shapes), not ORM objects — most of this codebase's business logic operates on plain `dict`s, not DB rows
- One assertion focus per test; group related tests with a `# ---` banner comment, not `@Nested` classes, unless the file already uses `class Test...` (see Tier 2)
- Naming: `test_<role_or_subject>_<behavior>` (e.g. `test_researcher_cannot_see_patient_name`), not `test_<method_name>`

### Tier 2 — Endpoint Tests via FastAPI `TestClient` (contract-focused)

Test that a FastAPI endpoint's request/response contract and auth/role checks work end-to-end. Mock every I/O boundary (S3 upload, the SQLite registry, the audit logger) with `monkeypatch`/`unittest.mock.patch` — there is no test database or container.

**When to write:** At least one happy-path + one error-path per endpoint (403 for a disallowed role, 422 for bad input), more as needed.

```python
# tests/unit/test_bulk_ingestion.py — real pattern from this repo
from unittest.mock import MagicMock, patch
import pytest
from fastapi.testclient import TestClient
from app.main import app


@pytest.fixture(autouse=True)
def _patch_s3():
    with patch("app.main.s3_upload", return_value=None), \
         patch("app.main.s3_upload_file", return_value=None):
        yield


@pytest.fixture(autouse=True)
def _patch_registry(monkeypatch):
    monkeypatch.setattr("app.main.register_document", lambda *a, **kw: MagicMock())
    monkeypatch.setattr("app.main.update_status", lambda *a, **kw: None)


@pytest.fixture()
def client():
    return TestClient(app)


class TestRbac:
    def test_billing_role_rejected_with_403(self, client):
        resp = client.post("/ingest/bulk", headers={"role": "billing"},
                           files=[("files", ("scan.pdf", b"%PDF-1.4 fake", "application/octet-stream"))])
        assert resp.status_code == 403
```

**Patterns:**
- **I/O boundaries**: `patch()`/`monkeypatch.setattr()` on the exact import path used inside the module under test (e.g. `"app.main.s3_upload"`, not `"storage.s3_client.upload"`) — mocks are patched where they're looked up, not where they're defined
- **Grouping**: `class TestRbac`, `class TestBatchSizeLimit`, etc. — one class per concern, plain `test_*` methods inside, no `@pytest.mark` decorators needed for grouping
- **Assertions**: assert HTTP status code, then response body shape (`resp.json()["job_ids"]`), then side effects (e.g. queue contents via a `_drain_queue()` helper)
- **Never raises**: helper functions that process one item in a batch (`_process_single_upload_bytes`) catch their own exceptions and return a `{"status": "rejected", ...}` dict, so one bad file doesn't fail the whole request — test that isolation explicitly (`test_register_error_for_one_file_does_not_block_others`)

## Steps

1. Read existing tests in `tests/unit/` for the module you're touching — patterns differ by whether the code under test does I/O
2. Identify acceptance criteria and endpoints to test
3. Write Tier 1 tests for pure business logic first
4. Write Tier 2 `TestClient` tests for any FastAPI endpoint change — cover every role that should be accepted/rejected, not just one of each
5. Run tests before considering the change done

## Running

```bash
# Full suite
pytest

# Single file
pytest tests/unit/test_bulk_ingestion.py

# Single class or test
pytest tests/unit/test_bulk_ingestion.py::TestRbac
pytest tests/unit/test_bulk_ingestion.py::TestRbac::test_billing_role_rejected_with_403

# With coverage (pytest-cov is in requirements.txt)
pytest --cov=. --cov-report=term-missing
```
