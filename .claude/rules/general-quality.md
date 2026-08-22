---
# Applies to all paths
---

# General Code Quality Rules

## GEN-01: Error handling <!-- severity: suggestion -->
New code paths must have appropriate error handling. Look for unhandled promise rejections, uncaught exceptions, missing try-catch around I/O operations, and missing error responses in API handlers.

## GEN-02: Logging <!-- severity: suggestion -->
Significant operations (API calls, database mutations, external service interactions, error paths) should have appropriate log statements. Log level should match severity — ERROR for failures, WARN for recoverable issues, INFO for key operations, DEBUG for details.

## GEN-03: Naming conventions <!-- severity: nit -->
Variable, function, class, and file names should be descriptive and follow the repo's established naming conventions. Avoid abbreviations unless domain-standard (e.g., `dto`, `req`, `res`). Boolean variables should read as predicates (e.g., `isActive`, `hasPermission`).

## GEN-04: Dead code <!-- severity: suggestion -->
Look for unused imports, unreachable code, commented-out code blocks, and unused variables or functions introduced in the diff. Commented-out code should be removed, not left as "just in case."

## GEN-05: Hardcoded values <!-- severity: suggestion -->
Magic numbers, hardcoded strings (URLs, credentials, feature flags, business logic thresholds) should be extracted to constants, configuration, or environment variables. Exception: test data and obvious values like `0`, `1`, `""`, `true/false`.

## GEN-06: Code duplication <!-- severity: suggestion -->
If the diff introduces logic substantially similar to existing code elsewhere, flag it. Suggest extracting to a shared utility, base class, or hook.

## GEN-07: API contract consistency <!-- severity: blocker -->
If the PR changes an API response shape, request shape, or database schema, verify that all consumers of that contract are updated. Check DTOs, mappers, serializers, and frontend API calls. When reviewing cross-repo API contracts: verify field names, enum values, and nullability match between frontend interfaces/types and backend DTOs/records — most modern client/server stacks pass bodies as-is with no mapping layer, so any mismatch surfaces only at runtime. Common mismatches: field name differences (`action` vs `acceptanceStatus`), enum value differences (`accept` vs `accepted`), optional vs required disagreements.

## GEN-08: Null safety <!-- severity: suggestion -->
Handle null/undefined/empty cases explicitly. Look for potential NPEs in Java (especially `.get()` on Optional, collection access, chained method calls) and undefined access in TypeScript (optional fields, API responses, URL params).

## GEN-09: TODO/FIXME/HACK comments <!-- severity: suggestion -->
If the diff introduces `TODO`, `FIXME`, or `HACK` comments, they should include a ticket ID or clear description of when they'll be addressed. Standalone TODOs without context become permanent technical debt.

## GEN-10: Commit message format <!-- severity: nit -->
Commits should follow the format specified in the repo's CLAUDE.md. Each commit should be a logical unit of work with a descriptive message.
