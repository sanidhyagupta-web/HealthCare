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
This is a single Python repo (no submodules) — run from the repo root. There is no
formatter/linter configured (no `black`/`ruff`/`flake8`/`mypy` in `requirements.txt` or any config
file) — do not invent one; skip format/static-analysis checks and run tests only:
```bash
# Tests for the affected test file(s) only
pytest tests/unit/test_<affected>.py

# Full suite is small enough to run when scope is unclear
pytest
```

### 5. Run Frontend Checks
There is no separate frontend toolchain here — no `package.json`, no JS/TS build. The "frontend"
(`ui/`) is plain Python (Streamlit pages) and is covered by the same `pytest` suite as the backend;
skip lint/format/type-check/build steps, none of which apply:
```bash
pytest tests/unit/test_<affected>.py
```

### 6. Run Ops Validation (if applicable)
This repo has no infrastructure-as-code (no Helm charts, Terraform, or Dockerfiles) — skip this
step unless a future change introduces one.

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
