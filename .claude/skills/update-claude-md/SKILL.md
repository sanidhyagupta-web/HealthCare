---
name: update-claude-md
description: Update CLAUDE.md files to reflect new patterns introduced by implementation. Run after user approves the implementation.
disable-model-invocation: true
---

# Update CLAUDE.md Files

Review the implementation and update relevant CLAUDE.md files to reflect new patterns, conventions, or services.

## Prerequisites
- All tasks complete, checks pass, user has approved the implementation

## Steps

1. **Find all CLAUDE.md files**: Search for all CLAUDE.md files dynamically using glob `**/CLAUDE.md` across all repositories. Read each one to understand what they currently document.

2. **Review what was implemented**: Read the execution state and implementation plan to understand what changed. Look at the actual commits to see what files were created or modified.

3. **Identify updates needed**: For each CLAUDE.md file, determine if the implementation introduced any of the following that should be documented:
   - New services or modules
   - New API endpoints or endpoint patterns
   - New components or UI patterns
   - New build commands or scripts
   - New environment variables
   - New database tables or migration patterns
   - New enums, constants, or shared types
   - New conventions or naming patterns
   - Changes to existing documented patterns

4. **Propose updates**: Present the proposed changes to the user for each CLAUDE.md file. Show which file will be updated, what will be added/modified, and why. Wait for approval before making changes.

5. **Apply approved changes**: Update only approved CLAUDE.md files. Maintain the existing style and structure of each file.

6. **Commit**: Commit CLAUDE.md changes using the commit message format from each repository's own CLAUDE.md. If updates span multiple repositories, commit in each repo following its own format.

## Rules
- Only update files relevant to changes made
- Do NOT remove existing content — only add or modify
- Keep updates concise and consistent with existing style
- Show proposed changes before committing
- This happens AFTER user approval but BEFORE pushing
- If no updates needed, state that and skip
