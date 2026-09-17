---
paths:
  - "ui/**/*.py"
---

# Frontend Coding Standards

<!-- CUSTOMIZE: Replace everything below with your project's frontend conventions -->

## FE-01: Component Patterns <!-- severity: suggestion -->
<!-- CUSTOMIZE: Your component conventions -->
- Functional components with hooks only (no class components)
- Explicit prop type interfaces
- Custom hooks for reusable logic (prefix with `use`)

## FE-02: Test Identifiers <!-- severity: blocker -->
<!-- CUSTOMIZE: Your test targeting strategy -->
All interactive elements MUST have a test identifier attribute:
```tsx
<button data-testid="submit-button">Submit</button>
```

## FE-03: Path Aliases <!-- severity: suggestion -->
<!-- CUSTOMIZE: Your import alias convention -->
Always use path aliases for shared resources. See tsconfig for the full list.

## FE-04: Commit Format <!-- severity: nit -->
<!-- CUSTOMIZE: Your frontend commit message format -->
```
[TICKET-ID][feat] commit message
```

## Verification Commands
After making changes, run only on changed files:
<!-- CUSTOMIZE: Your verification commands -->
```bash
# Lint changed files
your-lint-command path/to/ChangedFile.tsx

# Format changed files
your-format-command path/to/ChangedFile.tsx

# Type-check (read-only, safe to run on full app)
your-typecheck-command
```
IMPORTANT: Do NOT run full-project lint or format commands if they touch hundreds of files.
