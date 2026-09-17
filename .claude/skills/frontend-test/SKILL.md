---
name: frontend-test
description: Write unit tests for frontend components and hooks. Use when implementing tests or adding coverage.
---

# Write Frontend Unit Tests

Write unit tests for frontend components and hooks.

> The code examples below use React + Vitest + Testing Library + RTK Query. The **patterns** (mocking data hooks, rendering with providers, asserting via Testing Library queries, covering happy/error/loading states and user interactions) are the same across stacks — adapt the syntax to your framework and test runner.

## Setup

This repo has no React/JS frontend and no JS test runner. The only UI is a single-process
Streamlit app (`ui/*.py` — `login_page.py`, `upload_page.py`, `bulk_upload_page.py`,
`search_page.py`, `audit_page.py`, `streamlit_app.py`). `pytest` (the same runner used for
backend tests, see `backend-test`) is the only test infra in this repo — there is currently no
test file exercising `ui/*.py` (`tests/unit/` holds backend-only tests). To add coverage for a
Streamlit page, use `streamlit.testing.v1.AppTest` (bundled with the pinned `streamlit>=1.35`)
rather than the React/Testing-Library patterns below, which do not apply to this stack:

```python
from streamlit.testing.v1 import AppTest

def test_login_rejects_wrong_password():
    at = AppTest.from_file("ui/login_page.py")
    at.run()
    at.text_input[0].input("admin").run()
    at.text_input[1].input("wrong-password").run()
    at.button[0].click().run()
    assert at.error[0].value == "Invalid username or password."
```

The React + Vitest patterns below describe the general shape of frontend testing (mock the data
layer, render, assert on user-visible output) — treat them as illustrative only; there is no
Vitest/Jest/RTL in this repo to run them with.

## Steps

1. Read existing test files in the same app for patterns
2. Identify components/hooks to test
3. Create the test file following your project's location convention
4. Mock data hooks and state-management hooks as needed
5. Render with required providers (state, router, auth)
6. Assert using your test library's queries (e.g. `screen.getByTestId`, `screen.getByText`)
7. Run tests using `pytest` (see Running below).

## Patterns

### Component Test
```typescript
describe('ComponentName', () => {
  const mockData = { /* test data */ };

  beforeEach(() => {
    vi.mocked(useGetDataQuery).mockReturnValue({
      data: mockData,
      isLoading: false,
      isError: false,
    } as any);
  });

  it('should render data correctly', () => {
    render(<ComponentName />);
    expect(screen.getByTestId('data-display')).toBeInTheDocument();
  });

  it('should show loading state', () => {
    vi.mocked(useGetDataQuery).mockReturnValue({
      isLoading: true,
    } as any);
    render(<ComponentName />);
    expect(screen.getByTestId('loading-spinner')).toBeInTheDocument();
  });
});
```

### Hook Test
```typescript
import { renderHook } from '@testing-library/react';

describe('useCustomHook', () => {
  it('should return expected value', () => {
    const { result } = renderHook(() => useCustomHook(args));
    expect(result.current.value).toBe(expected);
  });
});
```

## Key Conventions
- Target elements with stable test selectors (e.g., `data-testid` attributes or accessible roles)
- Mock data-layer hooks, not the underlying fetch/HTTP layer
- Test behavior, not implementation details
- Cover: happy path, error states, loading states, user interactions

## Running

```bash
# Full suite (backend + any ui/ tests)
pytest

# Single test file
pytest tests/unit/test_login_page.py
```

There is no watch mode configured in this repo (no `pytest-watch`/`ptw` in `requirements.txt`) —
re-run `pytest` after each change.
