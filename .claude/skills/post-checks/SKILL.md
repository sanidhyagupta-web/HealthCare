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
Run tests for affected modules only — this repo has no formatter or static-analysis tool
configured (no `ruff`/`black`/`mypy` in `requirements.txt`, no lint config file), so `pytest` is
the only verification step:
```bash
pytest tests/unit/test_<affected_module>.py
# or, if the change is broad enough that per-file targeting isn't practical:
pytest
```

### 5. Run Frontend Checks
There is no separate frontend repo or JS toolchain — the only UI is the Streamlit app under
`ui/*.py`. There is no lint/format/type-check/build step for it (no `package.json`, no
TypeScript). If the change touched `ui/*.py`, at minimum start it and click through the affected
page to confirm it renders and the flow works — Streamlit has no static build step to catch
errors otherwise:
```bash
streamlit run ui/streamlit_app.py
```
If the change also touched `app/main.py` (the FastAPI bulk-ingest endpoint), verify it boots:
```bash
uvicorn app.main:app --reload
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
