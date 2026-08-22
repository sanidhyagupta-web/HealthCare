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
For each affected repository, read its CLAUDE.md for the testing and code quality commands.

### 4. Run Backend Checks
This is a single Python repo (`app/`, `ingestion/`, `indexing/`, `search/`, `security/`, `workers/`, etc.) with no configured formatter, linter, or type checker (no `ruff`/`black`/`flake8`/`mypy` config anywhere in the repo) — do not invent one. Run the test suite, scoped to the affected test files where possible:
```bash
# Whole suite
pytest

# Affected files only
pytest tests/unit/test_<affected_area>.py
```

### 5. Run Frontend Checks
The "frontend" is `ui/` (Streamlit, Python) — there is no separate JS toolchain (no `package.json`, no lint/build step) and no dedicated `ui/` tests exist yet. It's checked by the same `pytest` run as step 4, not a separate command:
```bash
pytest tests/unit/test_<affected_ui_area>.py   # if a test exists for the touched ui/ page
```

### 6. Run Ops Validation (if applicable)
Validate any modified infrastructure files (Helm charts, Terraform, YAML).

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
