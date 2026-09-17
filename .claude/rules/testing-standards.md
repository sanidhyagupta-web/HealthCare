---
# Applies to all paths
---

# Testing Standards

## TEST-01: New logic must have tests <!-- severity: suggestion -->
New business logic (service methods, utility functions, hooks, reducers) should have corresponding tests. Exception: trivial getters/setters, simple DTOs, and configuration classes.

## TEST-02: Test the unhappy path <!-- severity: suggestion -->
Tests should cover error cases, edge cases, and boundary conditions — not just the happy path. Look for: missing null/empty input tests, missing error response tests, missing boundary value tests (0, max, negative), missing permission-denied tests.

## TEST-03: Test naming <!-- severity: nit -->
Test names should describe the scenario and expected outcome, not just the method name. Follow the repo's existing test naming convention.

<!-- CUSTOMIZE: Replace examples below with your language's test naming pattern -->
**Bad**: `@Test void testCalculate() { ... }`
**Good**: `@Test void calculate_withNullInput_throwsIllegalArgumentException() { ... }`

## TEST-04: Mock boundaries, not internals <!-- severity: suggestion -->
Mocks should be used for external boundaries (databases, APIs, file systems, time) — not for internal classes being tested. If a test mocks most of the class under test, it's testing the mocks, not the code.

## TEST-05: Test data setup <!-- severity: nit -->
Test data should be created using builders, factories, or helper methods — not large blocks of inline construction. Shared test fixtures should be in a common test utility class, not duplicated across test files.

## TEST-06: Assertions <!-- severity: suggestion -->
Tests should have meaningful assertions — not just "no exception thrown." Each test should assert the specific expected outcome. Avoid asserting too many things in one test. Use descriptive assertion messages where supported.

## TEST-07: Integration test isolation <!-- severity: suggestion -->
Integration tests should not depend on execution order or shared mutable state. Each test should set up its own data and clean up after itself (or use transactions that roll back).

## TEST-08: Test coverage for API changes <!-- severity: suggestion -->
If the PR adds or modifies API endpoints, there should be integration tests verifying the request/response contract — status codes, response shapes, error cases, and authorization.

## TEST-09: Frontend component tests <!-- severity: suggestion -->
New components with non-trivial logic should have tests. Tests should verify user-visible behavior (what renders, what happens on click) — not implementation details.

## TEST-10: Snapshot tests <!-- severity: nit -->
Snapshot tests should be for stable, well-defined components — not large page-level components that change frequently. Large snapshots produce meaningless diffs that get rubber-stamped.
