---
name: frontend-test
description: Write unit tests for frontend components and hooks. Use when implementing tests or adding coverage.
---

# Write Frontend Unit Tests

Write unit tests for frontend components and hooks.

> The code examples below use React + Vitest + Testing Library + RTK Query. The **patterns** (mocking data hooks, rendering with providers, asserting via Testing Library queries, covering happy/error/loading states and user interactions) are the same across stacks — adapt the syntax to your framework and test runner.

## Setup

This project's "frontend" is `ui/` — a Streamlit (Python) app, not a React/TS app. There is no separate JS test runner (no `package.json` anywhere in the repo) and no existing tests target `ui/` yet — the same `pytest` setup used for the backend (see `backend-test`) is what to use here too. Streamlit pages read/write `st.session_state` directly (no store layer), so tests mock `streamlit.session_state` rather than a data-hook. Put new tests under `tests/unit/`, alongside the existing ones, following their naming (`test_<feature>.py`).

```python
# pytest + unittest.mock example — Streamlit has no official component-testing library
# for plain script-style pages, so page functions must be structured to accept
# injected state/mocks rather than reading st.* directly wherever possible.
from unittest.mock import patch, MagicMock
```

## Steps

1. Read existing test files in the same app for patterns
2. Identify components/hooks to test
3. Create the test file following your project's location convention
4. Mock data hooks and state-management hooks as needed
5. Render with required providers (state, router, auth)
6. Assert using your test library's queries (e.g. `screen.getByTestId`, `screen.getByText`)
7. Run tests using `pytest` — the same runner as the backend (no separate JS test runner exists in this repo).

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
# Whole suite (backend + ui/ tests together — one suite, one runner)
pytest

# Single test file
pytest tests/unit/test_<feature>.py

# Watch mode is not set up — no pytest-watch/pytest-xdist --looponfail configured
```
