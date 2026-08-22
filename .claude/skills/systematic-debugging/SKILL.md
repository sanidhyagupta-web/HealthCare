---
name: systematic-debugging
description: Use when something is broken, failing, or producing unexpected output. Mandatory root-cause investigation before any fix attempt. Prevents symptom-masking and fix stacking.
---

# Systematic Debugging

## Overview

This skill enforces a mandatory investigation-first approach before any fix is written. The most common debugging failure is attempting fixes before understanding the root cause, leading to symptom-masking and compounding issues.

**Absolute rule: NO FIXES WITHOUT ROOT CAUSE INVESTIGATION FIRST.**

## When to Use

Use this skill whenever:
- A test is failing
- A build is broken
- An endpoint returns unexpected data
- A feature is behaving incorrectly
- You have attempted one fix and it did not resolve the issue

## The 4 Mandatory Phases

### Phase 1: Root Cause Investigation

Before writing a single line of fix code:

1. **Read the full error message** — not just the first line. Stack traces, caused-by chains, and test assertion failures all contain the real signal.
2. **Reproduce it consistently** — confirm you can trigger the failure reliably before touching anything.
3. **Review recent changes** — run `git log --oneline -10` and `git diff HEAD~1` to see what changed.
4. **Gather evidence at boundaries:**
   - Backend: Add temporary log statements at service entry/exit points. Check what data is actually entering the service vs what is expected.
   - Frontend: Use browser devtools network tab. Check the actual request payload and response, not what you think is being sent.

### Phase 2: Pattern Analysis

1. **Find a working example** — find a similar feature or test that passes and compare it completely to the failing one.
2. **Identify exact differences** — list every difference, no matter how small. The root cause is often in something that looks inconsequential.
3. **Understand all dependencies** — for a failing test, understand every `@MockBean`, every `@BeforeEach`, every Testcontainers setup. For a failing component, trace the RTK Query cache state.

### Phase 3: Hypothesis and Testing

Apply the scientific method:

1. **Form ONE specific hypothesis** — "I believe X is happening because Y" with evidence.
2. **Test it with a single variable change** — change one thing, re-run, observe.
3. **NEVER proceed without verification** — if you cannot confirm the hypothesis with evidence, do not fix based on it.

**Red flags — stop and reassess if you observe these:**
- You have attempted 3+ fixes without the root cause being clear
- Each fix reveals a new problem
- You are "trying things" rather than testing hypotheses

### Phase 4: Implementation

Only after the root cause is confirmed:

1. **Write a failing test first** that demonstrates the bug (see `backend-test` or `frontend-test` skills for test patterns).
2. **Apply the single fix** that addresses the root cause.
3. **Verify the fix** — run the full test suite for the affected service/app, not just the one failing test.

## Platform-Specific Techniques

### Backend (Java / Spring Boot)

**Tracing a bug through the stack:**
```java
// Add temporary instrumentation at boundaries
log.debug("DEBUG [method]: input={}, computed={}", input, computedValue);
```

**Test pollution** — if a test passes in isolation but fails in suite:
- Run with `--tests "TestClass#testMethod"` in isolation first
- If it passes alone, you have test pollution
- Use `@DirtiesContext` or check `@BeforeEach`/`@AfterEach` for missing cleanup
- Check for shared static state or database rows not cleaned up between tests

**Testcontainers failures:**
- Container not starting: check Docker is running and port is free
- Schema mismatch: verify Flyway migrations run in correct order (check `V` prefix numbering)
- Feign client errors in tests: confirm `@MockBean` is applied for all Feign clients

**Timing-dependent failures:**
- Never use `Thread.sleep()` in tests — use `await().atMost(5, SECONDS).until(() -> condition)` (Awaitility)
- Check for race conditions in async Temporal workflows

### Frontend (React / TypeScript)

**RTK Query debugging:**
- Check browser devtools → Network → XHR to see actual requests
- Check Redux devtools to see actual cache state
- Verify `providesTags`/`invalidatesTags` match exactly — a typo means stale data
- Confirm `enhanceEndpoints()` is called before `injectEndpoints()`

**Component test failures:**
- `screen.getByTestId` fails: check the `data-testid` attribute is on the rendered element, not a wrapper
- RTK Query mock not working: verify `setupStore` has the correct mocked handlers
- Type errors: run `npx tsc --noEmit` to get the full compiler output

**Condition-based waiting (replace setTimeout):**
```typescript
// WRONG — flaky
await new Promise(resolve => setTimeout(resolve, 50))

// RIGHT — deterministic
await waitFor(() => expect(screen.getByTestId('result')).toBeInTheDocument())
```

## Common Mistakes to Avoid

| Mistake | Why it's wrong |
|---------|---------------|
| Fixing the first thing that looks wrong | You may fix a symptom, not the cause |
| Trying 3+ consecutive fixes without re-investigating | You are guessing, not debugging |
| Claiming "it should work now" without running verification | Unverified fixes are not fixes |
| Changing multiple variables at once to "try things" | You cannot isolate which change had which effect |
| Reading only the first line of a stack trace | The root cause is almost always in the `Caused by:` chain |
