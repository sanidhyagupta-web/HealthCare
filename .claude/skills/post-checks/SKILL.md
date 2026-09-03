---
name: post-checks
description: Run post-implementation verification — tests, code quality, and build checks across affected repositories.
disable-model-invocation: true
---

# Post-Implementation Checks

Run targeted tests and verify the implementation.

## Steps

### 1. Verify Completeness
Read `execution-state.md`. Check all tasks are complete. If any are incomplete or blocked, list them and ask the user how to proceed.

### 2. Verify New Tests Exist
Read the Testing Strategy from `implementation-plan.md`. Verify each planned test file was created under `tests/unit/`. Note any missing tests.

### 3. Read Verification Commands
This is a single Python repo (backend under `app/`, `ingestion/`, `workers/`, etc.; the Streamlit UI under `ui/`) with one shared test suite — there is no separate frontend build/lint toolchain to check.

### 4. Run Tests
Run pytest for the affected test files ONLY (not the full suite, unless the change is broad):
```bash
pytest tests/unit/test_<affected>.py
```
For coverage on the affected area:
```bash
pytest tests/unit/test_<affected>.py --cov
```

### 5. Code Quality
This repo has no configured linter, formatter, or type-checker (no ruff/black/mypy/flake8 config present). Do not invent one — if the task calls for adding one, that is a separate, explicit decision, not a post-check.

### 6. Streamlit Smoke Check (UI changes only)
For changes under `ui/`, confirm the affected page still imports and runs cleanly:
```bash
python -c "import ui.<changed_page>"
```
Prefer an `AppTest`-based test (see the `frontend-test` skill) over a manual `streamlit run` pass when possible.

### 7. Generate Verification Summary
Cover: test files run, test results, any skipped checks (and why), warnings.

### 8. Update Execution State
- All pass: set status to `CHECKS_COMPLETE`
- Any fail: set status to `CHECKS_FAILED` and log failures

## Rules
- Only test affected files — not the full suite, unless the change is broad
- Report failures clearly with file paths, test names, error messages
- Do NOT modify code in this step — only check and report
- If checks fail, inform the user and wait for instructions
