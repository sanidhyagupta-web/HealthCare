---
name: plan
description: Generate an implementation plan from finalized requirements. Explores the codebase and asks the user inline (via AskUserQuestion) when meaningfully different approaches exist, then writes implementation-plan.md.
disable-model-invocation: true
allowed-tools:
  - Read
  - Write
  - Edit
  - Glob
  - Grep
  - Bash
  - AskUserQuestion
---

# Requirements to Implementation Plan (sync)

Convert the finalized requirements document into an implementation plan with an ordered task list. When codebase exploration surfaces meaningfully different valid approaches, ask the user inline and continue with their choice — do not pause or write a separate options artifact.

## Steps

1. **Read requirements**: Read the finalized `requirements.md` from the execution folder.

2. **Read the code wiki** (if it exists):
   - Read `code-wiki/{project-id}/Features/index.md` — match ticket keywords to the Workflow Routing Rules table to identify which feature files are relevant
   - Read the identified feature files; for each, load only the sections listed in their `Workflow Loading Map` for `/plan` (typically: full file + Mandatory Dependencies from index.md)
   - From each feature file, extract: Invariants, Business Rules, Safe vs Dangerous Changes, and any shared contracts that affect this ticket
   - Build an **impact list**: which features, APIs, and shared contracts this ticket touches and what the downstream risk is
   - If `code-wiki/{project-id}/Features/index.md` does not exist yet, note it in the plan and run `/init-code-wiki` first
   - Treat what you read as **evidence, not current fact** — nothing keeps the code wiki current after a ticket merges, so verify any claim this plan depends on against the source

3. **Explore the codebase**:
   - Read ALL `CLAUDE.md` files at every directory level
   - Explore relevant source files to understand existing patterns, APIs, entities, components
   - Identify which services, modules, and screens are affected
   - Look at similar existing features for patterns to follow
   - If requirements include Figma links and Figma MCP is available, use `get_design_context` for component specs

4. **Assess alternatives**: Based on what you found in step 2, ask — *"Are there 2+ meaningfully different valid approaches here?"*

   **This triggers when** the codebase exploration reveals genuine architectural divergence:
   - Different design patterns (e.g., extend an existing abstraction vs. introduce a new one)
   - Different tradeoffs in complexity, correctness, or performance
   - Different migration strategies with different risk profiles

   **This does NOT trigger for**: style differences, minor implementation variations, or cases where one approach is clearly correct given existing patterns.

   **If no meaningful alternatives**: proceed to step 4.

   **If alternatives exist**: present them inline using `AskUserQuestion`. Use a single-select question with 2-4 options. Each option's `label` is the approach name (≤5 words); each option's `description` compresses the tradeoff signal — Summary / Tradeoffs / Risks / Effort — into one paragraph the user can scan.

   - Suggested question header: `Approach`
   - Suggested question text: `I see {N} meaningfully different ways to implement this. Which approach should I plan against?`
   - The user's selection is the **chosen approach**. Continue immediately to step 5 — do not write any artifact for the options.

5. **Validate plan references**:
   - For each file listed, verify it exists (or note as new file)
   - Check latest migration version numbers for sequential numbering
   - Verify entity/DTO signatures match plan assumptions

6. **Create `implementation-plan.md`** in the execution folder. If the user chose between alternatives at step 4, the `Key Decisions` section MUST name the chosen alternative and summarize the reasoning in 1-2 sentences. This preserves the architectural decision in the plan itself, removing the need for a separate options artifact.

7. **Present the plan** to the user for review and approval.

## Implementation Plan Structure

```markdown
# {TICKET-ID}: {Title} — Implementation Plan

## Overview
Brief summary (2-3 sentences).

## Key Decisions
Architectural/design decisions with justifications referencing codebase patterns. When the user chose between alternatives at step 4, name the chosen alternative here and summarize the reasoning (1-2 sentences).

## Impact Analysis
Features, APIs, and shared contracts this ticket touches and the downstream risk.
Populated from `code-wiki/{project-id}/Features/`. If the code wiki does not exist, state that here.

| Feature / Contract | Change Type | Downstream Risk |
|-------------------|-------------|-----------------|
| `{feature-name}` | {added/modified/removed} | {who breaks and how} |

## Cross-Repo Contracts
Define shared interfaces between repositories that parallel agents need to know about. This section ensures agents working on different repos stay aligned. **This is the ONLY section where code/schema definitions are allowed** — use them to eliminate ambiguity in names, types, and values.

Include precise definitions for:
- **Database schema**: Column names, types, constraints (SQL snippets)
- **API endpoints**: Method, path, request/response field shapes (field names and types only, not full implementations)
- **Shared enums with business values**: Names, numeric mappings, flags, labels (full enum definitions)
- **Shared constants**: Any values that must match exactly across repos

Example:
\`\`\`sql
-- Database contract
ALTER TABLE orders ADD COLUMN cancellation_reason VARCHAR(255);
\`\`\`
\`\`\`typescript
// DTO contract (field names and types only)
interface OrderResponse {
  id: number;
  status: string;
  cancellationReason?: string;
}
\`\`\`

The test: "Could two independent agents (one for BE, one for FE) implement their tasks without talking to each other and still produce code that integrates correctly?" If not, add more contract detail.

## Task List

### [BE] Task 1: {Short description}
- **Service**: {service name}
- **Files affected**: List of files
- **What to do**: Describe behavior, not code
- **Acceptance**: How to verify
- **Dependencies**: Tasks that must complete first

### [FE] Task 2: {Short description}
- **App**: {app name}
- **Files affected**: List of files
- **What to do**: Description
- **Design reference**: {Figma node ID or N/A}
- **Acceptance**: How to verify
- **Dependencies**: Dependencies

## Implementation Order
Recommended order with parallelization notes and critical path.

## Testing Strategy
Specific integration tests, frontend flows, manual verification steps.

## Test Case Outline

For each task, derive test scenarios from the ticket's acceptance criteria. Every AC must be covered by at least one test. Group backend tests into two tiers:

**Tier 1 — Service tests** (mock repositories, test logic):
Cover all AC scenarios, business rule branches, validation, and edge cases. Fast TDD cycles.

**Tier 2 — Integration tests** (real DB, test contracts):
At least one happy-path + one error-path per endpoint, more as needed based on ticket ACs and error cases. Verify API shapes, DB persistence, auth.

### [BE] Task 1 Tests

#### Tier 1 — Service Tests (`OrderServiceTest`)
| Test | AC | Scenario | Expected |
|------|----|----------|----------|
| shouldCancelOrder_whenDraftStatus | AC-001 | Cancel a DRAFT order | Status → CANCELLED, cancelledAt set |
| shouldThrow409_whenAlreadyCancelled | AC-001 | Cancel an already CANCELLED order | ConflictException |
| shouldThrow400_whenInvalidStatus | AC-002 | Cancel with invalid status transition | ValidationException |

#### Tier 2 — Integration Tests (`OrderControllerIT`)
| Test | AC | Scenario | Expected |
|------|----|----------|----------|
| shouldCancelOrder_returns200 | AC-001 | PATCH /v1/orders/{id}/cancel | 200, DB status = CANCELLED |
| shouldReturn409_whenAlreadyCancelled | AC-001 | PATCH cancel on CANCELLED order | 409 |

### [FE] Task 2 Tests
| Test | AC | Scenario | Expected |
|------|----|----------|----------|
| renders form with all fields | AC-003 | Mount component | All inputs visible |
| submits and shows success | AC-004 | Fill form, click submit | API called, toast shown |
| shows validation error | AC-005 | Submit empty form | Error message displayed |
```

## Rules

### Code Snippet Policy
- **Code/schema IS allowed** in the Cross-Repo Contracts section — for database schema, DTO/interface field shapes, enum definitions with business values, and API signatures
- **Code is NOT allowed** in the Task List section — describe WHAT to do, not HOW to write the code. The implementing agent will explore the codebase and follow existing patterns
- The distinction: contracts define the **interface** (names, types, values that must match across repos); tasks describe the **behavior** (what the code should do)

### Task Structure
- Every task MUST be marked `[BE]`, `[FE]`, or `[Ops]`
- Tasks should be small enough to be completed and committed independently
- Tasks within the same repo should be ordered by dependency
- Each task MUST have clear acceptance criteria that can be verified
- If a task requires creating a new file, state that explicitly; otherwise assume modification of existing files
- Every task MUST have at least one test scenario in the Test Case Outline
- Test scenarios should cover happy path AND at least one error/edge case per task

### Plan Validation
- Every file path in the task list MUST be verified against the actual codebase — never assume a path exists without checking
- Migration version numbers MUST be checked against the latest existing migration in each service
- If the plan references an entity or DTO, verify its current signature before assuming fields or methods exist

### Cross-Repo
- Cross-repo dependencies MUST be documented in the "Cross-Repo Contracts" section with precise definitions
- Focus on WHAT needs to change in each task — the implementing agent will explore the codebase and determine the best approach based on existing patterns
- Reference existing codebase patterns in Key Decisions to guide the implementing agent

### Mode Boundary
- This skill resolves alternatives inline via `AskUserQuestion` and always produces `implementation-plan.md`.
