---
name: audit-claude-md
description: Audit and consolidate all CLAUDE.md files for accuracy, staleness, and bloat. Periodic maintenance task.
disable-model-invocation: true
---

# Audit and Consolidate CLAUDE.md Files

Review all CLAUDE.md files for accuracy, staleness, and bloat. This is a periodic maintenance task, not part of the regular feature workflow.

## When to Run

- After a batch of features has been shipped (e.g., every sprint or every 10 tickets)
- When CLAUDE.md files feel too long or contain outdated references
- After significant refactoring that may have invalidated documented patterns

## Steps

1. **Find all CLAUDE.md files**: Glob `**/CLAUDE.md` across all repositories.

2. **For each file, audit every section**:
   - **Verify file paths**: Check all referenced paths still exist
   - **Verify patterns**: Check documented patterns match actual codebase
   - **Verify commands**: Test build/test/lint commands still work
   - **Check for duplicates**: Identify content in multiple files — keep in most specific file
   - **Check for bloat**: Identify verbose sections, consolidate similar entries

3. **Propose changes** for each file:
   - Content to remove (with reason)
   - Content to update (with reason)
   - Content to consolidate (with reason)

4. **Apply approved changes** and commit per repo using each repo's commit format.

5. **Report**: Lines before/after per file, what was removed/updated/consolidated.

## Rules
- Always verify against actual codebase before removing content
- When in doubt, keep and flag for user review
- Maintain existing style and structure
- Do not add new content — only audit, consolidate, clean up
