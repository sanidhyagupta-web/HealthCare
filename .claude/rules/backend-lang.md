---
paths:
  - "app/**/*.py"
  - "db/**/*.py"
  - "ingestion/**/*.py"
  - "workers/**/*.py"
  - "queues/**/*.py"
  - "search/**/*.py"
  - "llm/**/*.py"
  - "indexing/**/*.py"
  - "monitoring/**/*.py"
  - "evaluation/**/*.py"
  - "security/**/*.py"
  - "storage/**/*.py"
  - "mlx_adapter/**/*.py"
---

# Backend Coding Standards

<!-- CUSTOMIZE: Replace everything below with your project's backend conventions -->

## Principles
- KISS — prefer the straightforward solution over clever abstractions
- YAGNI — don't build for hypothetical future requirements

## BE-01: Architecture <!-- severity: suggestion -->
<!-- CUSTOMIZE: Your layered architecture pattern -->
- Follow the N-layer pattern established in the codebase
- Controllers/handlers handle HTTP concerns only
- Services contain all business logic
- Never call data layer directly from controllers

## BE-02: Data Model Conventions <!-- severity: suggestion -->
<!-- CUSTOMIZE: Your DTO/model conventions -->
- How DTOs should be annotated/structured
- Naming conventions for request/response objects

## BE-03: Security Annotations <!-- severity: blocker -->
<!-- CUSTOMIZE: Your auth/security patterns -->
- How endpoints should be secured
- Service-to-service auth patterns

## BE-04: Code Quality <!-- severity: suggestion -->
<!-- CUSTOMIZE: Your formatting and analysis commands -->
```bash
# Format code
your-format-command

# Static analysis
your-lint-command

# Compile check
your-compile-command
```

## BE-05: Commit Format <!-- severity: nit -->
<!-- CUSTOMIZE: Your backend commit message format -->
```
TICKET-123: commit message
```

## Verification Checklist
After making changes, run these in order:
<!-- CUSTOMIZE: Your verification steps -->
1. Format code
2. Verify compilation
3. Run relevant tests only (not the full suite)
