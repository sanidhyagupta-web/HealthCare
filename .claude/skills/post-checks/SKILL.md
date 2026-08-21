---
name: post-checks
description: Run post-implementation verification — tests, code quality, and build checks across affected repositories.
disable-model-invocation: true
---

# Post-Implementation Checks

Run targeted integration tests and verify the implementation across all affected repositories.

## Steps

### 1. Verify Completeness
Read `execution-state.md`. Check all tasks are complete. If any are incomplete or blocked, list them and ask the user how to proceed.

### 2. Verify New Tests Exist
Read the Testing Strategy from `implementation-plan.md`. Verify each planned test file was created. Note any missing tests.

### 3. Read Verification Commands
This is a single Python repo (no separate backend/frontend repos, no ops repo) — there is one
command set below, not one per repo. There is no lint/format/type-check tooling configured
(no `pyproject.toml`, no ruff/black/flake8/mypy config) — do not invent one; `pytest` is the only
verification gate that exists.

### 4. Run Tests
Run tests scoped to the modules actually touched, not the full suite, unless the change is
repo-wide (e.g. a shared dependency like `security/access_control.py` or `app/config.py`):
```bash
# Whole affected test file
pytest tests/unit/test_bulk_ingestion.py

# Single test/class
pytest tests/unit/test_bulk_ingestion.py::TestRbac

# Full suite, when the change is broad or before considering work fully done
pytest

# With coverage
pytest --cov=. --cov-report=term-missing
```

### 5. Frontend (`ui/`) Checks
`ui/` is Streamlit (Python), not a separate JS app — there is no lint/build/type-check step for it.
If `ui/` tests exist for the touched page (see `frontend-test` skill), run them the same way as step 4.

### 6. Ops Validation
Not applicable — this repo has no Helm/Terraform/Kubernetes ops directory. Skip this step.

### 7. Generate Verification Summary
Cover: services/apps tested, test results, code quality results, build results, warnings.

### 8. Update Execution State
- All pass: set status to `CHECKS_COMPLETE`
- Any fail: set status to `CHECKS_FAILED` and log failures

## Rules
- Only test affected services/apps — not the full suite
- Report failures clearly with file paths, test names, error messages
- Do NOT modify code in this step — only check and report
- If checks fail, inform the user and wait for instructions
