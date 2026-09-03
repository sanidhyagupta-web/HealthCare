---
name: backend-test
description: Write backend tests using a two-tier strategy — service tests for business logic, integration tests for API/DB contracts.
---

# Write Backend Tests

Write tests for a backend service using a two-tier strategy that follows the test pyramid.

> This repo uses Python + pytest + FastAPI's `TestClient` + `unittest.mock`/`monkeypatch`. The **strategy** (Tier 1 mocked service tests + Tier 2 real-DB integration tests) is the same as in other stacks — see `tests/unit/test_bulk_ingestion.py` and `tests/unit/test_dicom_parser.py` for existing examples to follow.

## Two-Tier Strategy

### Tier 1 — Service Tests (fast, numerous)

Test business logic in isolation. Mock external boundaries (S3, DB registry writes, audit logging). Cover all acceptance criteria scenarios, business rule branches, validation, and edge cases.

**When to write:** Every AC scenario, every business logic branch, every validation rule, every error case.

```python
# pytest example — see tests/unit/test_dicom_parser.py for the real version
import pytest

@pytest.fixture
def ct_bytes() -> bytes:
    return _load_fixture("ct_scan.dcm")

def test_raises_on_invalid_bytes():
    with pytest.raises(ValueError):
        parse_dicom(b"not a dicom file")

def test_extracts_modality(ct_result):
    assert ct_result["modality"] == "CT"
```

**Patterns:**
- Plain `pytest` functions (`test_*`), grouped with a `class Test*` only when several cases share request/response setup (see `TestRbac` in `tests/unit/test_bulk_ingestion.py`)
- `@pytest.fixture(autouse=True)` to patch external boundaries (S3, registry, audit logger) for every test in the module via `monkeypatch.setattr(...)` or `unittest.mock.patch(...)`
- `@pytest.fixture` for shared byte/data fixtures
- Naming: `test_<behavior>_<condition>` (e.g. `test_billing_role_rejected_with_403`)

### Tier 2 — Integration Tests (slower, contract-focused)

Test that layers wire together correctly. Verify API contracts (endpoint paths, status codes, request/response shapes, RBAC) via FastAPI's `TestClient` against the real SQLite DB (`db/database.py`) — this repo has no separate integration-test DB or Testcontainers setup; the SQLite file created by `init_db()` is the real engine production runs.

**When to write:** At least one happy-path + one error-path per endpoint (see `TestRbac` in `tests/unit/test_bulk_ingestion.py` for the pattern: role accepted / role rejected with 403).

```python
from fastapi.testclient import TestClient
from app.main import app

@pytest.fixture()
def client():
    return TestClient(app)

def test_doctor_role_accepted(client):
    resp = client.post("/ingest/bulk", headers={"role": "doctor"},
                        files=[_make_upload("scan.pdf", _PDF_BYTES)])
    assert resp.status_code == 200
```

**Patterns:**
- **Data setup**: Insert via the real SQLAlchemy session/registry functions (`ingestion/registry.py`), not mocks, for DB-contract tests
- **External-service mocking**: Mock only true external boundaries — S3 (`storage/s3_client.py`), audit logging — via `patch`/`monkeypatch`, autouse fixtures
- **Assertions**: Assert HTTP status code + response body + (for DB-contract tests) DB state via real reads
- **Cleanup**: Drain in-memory queues (`queues.parsing_queue`) before and after each test (see `_clear_queue` fixture)

## Steps

1. Read the relevant `AiHarness/skills/*.md` file (e.g. `access-control.md`, `document-ingestion.md`) and existing tests under `tests/unit/` for patterns
2. Identify acceptance criteria and endpoints to test
3. **Write Tier 1 service tests first** — cover all AC scenarios and logic branches, mocking S3/DB-registry/audit calls
4. **Write Tier 2 integration tests** — cover the `/ingest/bulk` (or other FastAPI endpoint) contract via `TestClient`
5. Group related cases in a `class Test*` only when it clarifies intent; otherwise flat `test_*` functions
6. Run tests with `pytest`

## Running

```bash
# Full suite
pytest

# Single test file
pytest tests/unit/test_bulk_ingestion.py

# Single test
pytest tests/unit/test_bulk_ingestion.py::TestRbac::test_doctor_role_accepted

# With coverage (pytest-cov is in requirements.txt)
pytest --cov
```
