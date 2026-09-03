---
name: requirements
description: Extract requirements from a ticket. Creates a requirements document and clarifications file in the execution folder.
disable-model-invocation: true
argument-hint: <ticket-id>
---

# Extract Requirements from Ticket

You are creating a requirements document from a ticket. This is the first step in the AI-assisted development workflow.

## Input

The ticket ID is: `$ARGUMENTS`

If `$ARGUMENTS` is empty, respond with:
> **Usage**: `/requirements <ticket-id>`
> Example: `/requirements PROJ-123`

Then stop.

## Steps

1. **Create the execution folder**: `docs/execution/{TICKET-NUMBER}-{ticket-summary}/`
   - Use kebab-case for the summary (e.g., `PROJ-123-user-profile-settings`)

2. **Fetch ticket content**: If a ticket system MCP is available, read the ticket content directly using the ticket ID. Also read sub-issues and comments. If not available, ask the user to paste the full ticket content.

3. **Extract Figma design context (if available)**: If the ticket contains Figma URLs and Figma MCP is available:
   - Use `get_screenshot` to view the linked designs visually
   - Use `get_metadata` to understand the design structure
   - Compare the design against ticket description and acceptance criteria — add discrepancies as clarification entries
   - Use the visual understanding to write more precise descriptions in the UI Screens Affected section
   - Record Figma file key and node IDs in Reference Materials so downstream skills can fetch design context
   - If Figma MCP is not available, just record the URLs as-is

4. **Create `requirements.md`** in the execution folder using the structure below.

5. **Create `clarifications.md`** in the execution folder with structured questions for any ambiguities.

6. **Stop and inform the user**: Tell them to review `clarifications.md`, fill in the answers, then run `/clarifications`. If no clarifications needed, tell them to proceed to `/plan`.

## Requirements Document Structure

```markdown
# {TICKET-ID}: {Title}

## Metadata

| Field | Value |
|-------|-------|
| **Ticket ID** | {ID} |
| **Priority** | {Priority} |
| **Project** | {Project} |
| **Design** | {Links to Figma or other designs} |

## Problem Statement
What problem does this feature solve? Why does it matter? (2-3 sentences)

## Goals
2-4 clear, measurable outcomes.

## Key Concepts
Define domain-specific terms, models, or logic rules. Use tables for structured data.

## User Stories
"As a [role], I want [feature], so that [benefit]" format.

## Acceptance Criteria
Given/When/Then format.

## UI Screens Affected
List all screens/components that need changes. Do NOT describe implementation.

## Open Questions
Unresolved questions from comments or ambiguities.

## Related Tickets
| Ticket | Description |
|--------|-------------|

## Reference Materials
Links to designs, recordings, attached files.
```

## Clarifications Document Structure

```markdown
# Clarifications: {TICKET-ID}

**Status**: PENDING

**Instructions**: Answer each question below. Select from suggested options or provide a custom answer. Once answered, run `/clarifications`.

---

## Q1: {Clear, specific question}
**Context**: {Why this matters}
**Options**:
- A) {Option}
- B) {Option}
- C) {Option}
**Answer**: _[fill in]_
**Notes**: _[optional]_

---
```

## Rules

- Do NOT include implementation breakdown, technical tasks, or story point estimates
- Do NOT prescribe solutions — only capture WHAT is needed, not HOW
- Preserve ambiguity where it exists — move it to `clarifications.md` rather than guessing
- Keep the requirements document concise — the AI will explore the codebase for context during planning
- Use tables for structured data (codes, mappings, reason types)
- Extract domain-specific enums/types that will be needed (e.g., status codes, reason types, category names)
- Every open question in the ticket or its comments should become a clarification entry
- If the ticket has sub-issues, incorporate their requirements into the main document and list them in Related Tickets

## Goal

Give an implementing AI everything it needs to understand the business requirements while letting it determine the technical approach based on the actual codebase.
