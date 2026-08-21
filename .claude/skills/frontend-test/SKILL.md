---
name: frontend-test
description: Write unit tests for frontend components and hooks. Use when implementing tests or adding coverage.
---

# Write Frontend (Streamlit) Tests

The "frontend" here is `ui/` — a single-process Streamlit app (`streamlit_app.py`, `login_page.py`,
`search_page.py`, `upload_page.py`, `bulk_upload_page.py`, `audit_page.py`), not a separate
React/TS app. There are currently **no tests under `ui/`** (`tests/unit/` only covers the backend) —
use pytest with Streamlit's own `AppTest` harness (`streamlit.testing.v1`, bundled with the
`streamlit>=1.35` dependency already in `requirements.txt`) rather than introducing a JS test
toolchain that has nothing else in this repo to sit alongside.

## Setup

Put new tests in `tests/unit/test_<page_name>.py`, following the same layout as the backend tests.
`AppTest.from_file()` runs a page script in a simulated session without a browser.

```python
from streamlit.testing.v1 import AppTest

def test_login_rejects_bad_password():
    at = AppTest.from_file("ui/login_page.py").run()
    # ... interact with at.text_input, at.button, then assert on at.session_state / at.error
```

## Steps

1. Read `security/auth.py` and the target page module first — most `ui/` pages gate on
   `is_authenticated()` / `current_user()` from `security.auth`, so tests usually need to seed
   `at.session_state` before `.run()` rather than driving the real login form each time
2. Identify the page(s) and user-visible behavior to test (what renders, what happens on submit/click)
3. Create `tests/unit/test_<page_name>.py`
4. Seed `st.session_state` (via `AppTest.session_state`) for role/department instead of mocking a
   data-fetching hook — this app has no RTK/TanStack-style data layer, session state *is* the state
5. Assert on the `AppTest` result tree (`at.error`, `at.success`, `at.markdown`, `at.text_input`,
   widget `.value`), not on implementation details of how a page function is written
6. Run with `pytest`, same as backend tests

## Patterns

### Page Test — unauthenticated gate
```python
from streamlit.testing.v1 import AppTest

def test_streamlit_app_shows_login_when_unauthenticated():
    at = AppTest.from_file("ui/streamlit_app.py").run()
    assert not at.session_state.get("authenticated", False)
    assert len(at.text_input) >= 2  # username + password fields from login_page
```

### Page Test — role-gated content
```python
def test_audit_page_visible_to_admin():
    at = AppTest.from_file("ui/audit_page.py")
    at.session_state["authenticated"] = True
    at.session_state["role"] = "admin"
    at.session_state["department"] = "general"
    at.session_state["username"] = "admin"
    at.run()
    assert not at.exception
```

### Login Form Test
```python
def test_login_form_rejects_wrong_password():
    at = AppTest.from_file("ui/login_page.py").run()
    at.text_input(key=None)[0].input("admin").run()  # username field
    at.text_input(key=None)[1].input("wrong-password").run()
    at.button[0].click().run()
    assert at.error  # "Invalid username or password."
```

## Key Conventions
- Test through `security.auth` (`login`, `is_authenticated`, `current_user`) rather than duplicating
  its hardcoded `_USERS` table in test fixtures — import and reuse it, or monkeypatch it for a
  synthetic user, don't hand-roll a second fake user store
- Cover: unauthenticated redirect to login, per-role visibility, and any error path a page renders
  (`st.error(...)` calls) — not just the happy render
- Test naming matches the backend convention: `test_<subject>_<expected_behavior>`

## Running

```bash
# Full suite (backend + any ui/ tests)
pytest

# Just the frontend tests
pytest tests/unit/test_login_page.py

# With coverage
pytest --cov=ui --cov-report=term-missing
```
