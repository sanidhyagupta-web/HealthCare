---
name: frontend-test
description: Write unit tests for frontend components and hooks. Use when implementing tests or adding coverage.
---

# Write Frontend Unit Tests

Write tests for the Streamlit UI (`ui/`).

> This repo's "frontend" is a Streamlit app (`ui/streamlit_app.py` and its pages), not a JS framework — there is no React/Vue/Jest/Vitest here. The test runner is the same `pytest` used for the backend (see `requirements.txt`); there are currently no tests under `ui/`, so treat this as backfilling coverage, not following an established pattern in this repo.

## Setup

Streamlit ships a built-in headless test harness, `streamlit.testing.v1.AppTest`, which runs a page script without a browser and exposes rendered elements for assertions. Prefer it over trying to unit-test page functions directly, since page modules call `st.*` at import time.

```python
from streamlit.testing.v1 import AppTest

def test_login_rejects_bad_password():
    at = AppTest.from_file("ui/login_page.py").run()
    at.text_input(key="Username").input("admin").run()
    at.text_input(key="Password").input("wrong-password").run()
    at.button[0].click().run()
    assert at.error[0].value == "Invalid username or password."
```

## Steps

1. Read the target page module in `ui/` (e.g. `login_page.py`, `search_page.py`) to see what it renders and what session state it depends on
2. Identify the user-visible behavior to test: what renders, what happens on submit/click, what error states look like
3. Create the test file under `tests/unit/` following this repo's existing naming (`test_<feature>.py`)
4. Use `AppTest.from_file(...)` to drive the page; set `at.session_state[...]` directly to simulate an already-authenticated user (mirrors what `security/auth.py:login()` sets) rather than re-implementing login in every test
5. Mock data-layer calls (search pipeline, ingestion API calls) the same way backend tests do — `unittest.mock.patch`/`monkeypatch` — not the underlying HTTP/DB layer
6. Assert on rendered output (`at.error`, `at.success`, `at.text_input`, `at.button`, etc.), not internal function calls
7. Run with `pytest`

## Key Conventions
- Mock data-layer calls (search/ingest functions), not `st.*` itself
- Test behavior, not implementation details — assert what's rendered, not which internal function ran
- Cover: happy path, error states (invalid login, rejected role), and user interactions (button clicks, form submission)

## Running

```bash
# Full suite
pytest

# Single test file
pytest tests/unit/test_login_page.py
```
