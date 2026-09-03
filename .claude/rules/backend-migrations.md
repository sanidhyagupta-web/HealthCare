---
paths:
  - "**/migration*/**/*.sql" # <!-- CUSTOMIZE: glob pattern for migration files -->
---

# Database Migration Conventions

<!-- CUSTOMIZE: Replace with your migration tool's conventions (Flyway, Prisma, Alembic, etc.) -->

## File Naming
<!-- CUSTOMIZE: Your migration naming convention -->
- Versioned: `V{version}__{description}.sql` — run once, never modified after merge
- Repeatable: `R__{description}.sql` — re-run when content changes (for seed data)

## Version Numbering
<!-- CUSTOMIZE: Your version numbering scheme -->
- Check the latest existing migration version before creating a new one
- Use sequential numbering

## Rules
- NEVER modify an existing versioned migration that has been applied/merged
- Always create a new migration for changes
- Use repeatable scripts for seed data and reference data that may change
- Test migrations locally before committing
