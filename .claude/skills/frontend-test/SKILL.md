---
name: frontend-test
description: Write unit tests for frontend components and hooks. Use when implementing tests or adding coverage.
---

# Write Frontend Unit Tests

Write unit tests for frontend components and hooks.

> The code examples below use React + Vitest + Testing Library + RTK Query. The **patterns** (mocking data hooks, rendering with providers, asserting via Testing Library queries, covering happy/error/loading states and user interactions) are the same across stacks — adapt the syntax to your framework and test runner.

## Setup

<!-- CUSTOMIZE: Where your project keeps tests (e.g. `__tests__/` directories, `*.test.ts` siblings, a separate test root) -->

```typescript
// React + Vitest + Testing Library example — adapt to your framework
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { vi } from 'vitest';
```

## Steps

1. Read existing test files in the same app for patterns
2. Identify components/hooks to test
3. Create the test file following your project's location convention
4. Mock data hooks and state-management hooks as needed
5. Render with required providers (state, router, auth)
6. Assert using your test library's queries (e.g. `screen.getByTestId`, `screen.getByText`)
7. Run tests using your project's test runner. <!-- CUSTOMIZE: e.g. `yarn test`, `npm test`, `vitest`, `jest` -->

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

<!-- CUSTOMIZE: Replace with your project's test commands -->
```bash
<your-test-runner> <test-file>
<your-test-runner> --watch   # Watch mode
```
