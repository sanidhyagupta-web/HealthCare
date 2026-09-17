---
name: implement-code
description: Implement tasks from an approved implementation plan. Spawns parallel agents per repository with verification and commits.
disable-model-invocation: true
---

# Implement Tasks from Plan

Implement the tasks from the implementation plan, working across repositories in parallel.

## Steps

### 1. Check State
Read `execution-state.md`. If tasks are already marked complete, resume from the first incomplete task.

### 2. Get Base Branch
If not set in `execution-state.md`, ask the user for the base branch (e.g., `develop`, `main`). Record it.

### 3. Update State
Set status to `IN_PROGRESS`. Update the ticket tracker if integration is available.

### 4. Create Branches
For each affected repository, create a feature branch from the base branch:
- Naming: `{ticket-id}-{short-summary}` (e.g., `ABC-123-user-profile-cleanup`)
- Use the ticket ID for the branch name — this must match the prefix used in commit messages.
- Record branch names in `execution-state.md`
- If resuming, check out existing branches instead.

### 5. Choose Execution Strategy

Review the implementation plan's Cross-Repo Contracts and task dependencies:

- **Use parallel execution** (default) when: contracts are simple (adding fields to existing DTOs, new endpoints with straightforward shapes), and backend/frontend tasks are mostly independent.
- **Use sequential execution** (backend first, then frontend) when:
  - The API shape is uncertain or complex (new resource types, nested structures, pagination changes)
  - Frontend tasks depend heavily on the exact response shape from new backend endpoints
  - The plan introduces new inter-service communication patterns

For sequential execution: run the BE agent first, verify the API works as expected, then pass the actual API response shapes to the FE agent instead of relying solely on the contracts.

### 6. TDD Implementation

Implementation follows three sequential phases per task. Each phase must complete before the next begins. This ensures tests encode **expectations** (what the code *should* do) rather than **observations** (what the code *does* do).

**You MUST use the `Agent` tool to implement tasks. Do NOT implement tasks inline in this session — this is mandatory, not optional, even for a single-repo ticket.**

Group by repository. For each repository with tasks, invoke the `Agent` tool with the appropriate subagent type:
- **Backend**: `subagent_type: backend-implementer`
- **Frontend**: `subagent_type: frontend-implementer`

When tasks across repos are independent (per Step 5), dispatch all agents in a single message so they run in parallel. When sequential execution is required, dispatch backend first, wait for completion, then dispatch frontend.

**Each agent receives** (include all of this in the `prompt` field):
- Full implementation plan (including cross-repo contracts and Test Case Outline)
- Tasks assigned to their repository
- Repository path and branch name

**Each agent, for each task, follows three phases**:

#### Phase 1: Code Stubs (Compile but Do Nothing)
Create minimal empty classes, methods, interfaces, and components with correct signatures. No business logic.
- **BE**: Empty controller methods (return null/empty), empty service methods, entity classes with fields only, DTOs, repository interfaces
- **FE**: Empty component shells (return placeholder JSX), empty hook functions, TypeScript interfaces/types, API endpoint definitions
- Run compilation/type-check to verify stubs are valid

#### Phase 2: Write Full Tests Against Stubs (Red)
Write **complete, real tests** — not skeletons or TODOs. Tests encode expected behavior from acceptance criteria and the Test Case Outline. All tests FAIL because stubs have no logic.
- **BE**: Two-tier tests per `backend-test` skill — Tier 1 service tests (mock repos, all AC scenarios and logic branches) + Tier 2 integration tests (real DB, API/DB contracts, at least one happy + one error per endpoint, more as ticket ACs demand). Most test volume is Tier 1 for fast TDD cycles.
- **FE**: Full component/hook tests per the `frontend-test` skill. Assert visible output, user interactions, API calls.
- Run tests to confirm they all FAIL

#### Phase 3: Implement Logic (Green)
Implement actual business logic in the stubs to make the failing tests pass. Do NOT modify test assertions to match implementation.
- Follow existing codebase patterns
- Iterate: implement → run tests → fix → repeat until all green
- After all tests pass: run full verification checks (code quality, build)
- Commit using the repo's commit message format
- Report: task number, commit hash, issues

### 7. Update State After Each Task
Mark complete with commit hash. Add log entry.

### 8. Final State Update
Set status to `IMPLEMENTATION_COMPLETE` when all tasks are done.

## Agent Instructions Template

```
You are implementing tasks for the {REPO-NAME} repository.

Repository path: {absolute path}
Branch: {branch-name}
Ticket: {ticket-id}

## Cross-Repo Contracts
{paste from implementation plan}

## TDD Workflow (mandatory for each task)

You MUST implement each task in three phases:

**Phase 1 — Stubs**: Create empty classes/methods/components with correct signatures. Verify compilation.
**Phase 2 — Tests**: Write full tests against the stubs using the Test Case Outline below. All tests must FAIL. Do NOT write tests that pass against empty stubs — if a test passes before logic exists, the test is not asserting behavior correctly.
**Phase 3 — Logic**: Implement business logic to make tests pass. Do NOT modify test assertions to match your implementation — if a test fails, fix the implementation, not the test (unless the test has a genuine bug).

## Test Case Outline
{test scenarios from plan's Test Case Outline for this repo's tasks}

## Your Tasks (implement in order, each using the 3-phase TDD workflow above)
{tasks for this repo}

## Rules
- FIRST: Read the repository's CLAUDE.md for commit format, verification commands, conventions
- Follow existing patterns — explore similar features for reference
- If a task has a Figma "Design reference", use Figma MCP to fetch design specs
- After each task: run verification checks from the CLAUDE.md
- Fix check failures before committing
- Commit each task separately using the repo's commit message format
- Do NOT modify files outside your assigned tasks
- Report after each task: task number, files changed, commit hash, issues
```

## Handling Failures

When any check, build, or test fails, invoke the `systematic-debugging` skill before attempting any fix.

- **Check/test failures**: Use `systematic-debugging` — investigate root cause first, then fix. Do not attempt multiple consecutive fixes without re-investigating. If the fix requires changes beyond the task scope, note it in execution state and move on.
- **Build failures**: Use `systematic-debugging` — read the full compiler error (not just the first line), trace the dependency that broke, apply a single targeted fix. If fixing requires modifying a previous task's output, note the dependency issue in execution state.
- **Blocked tasks**: If a task cannot be completed (e.g., missing dependency, unclear requirement), mark it as `BLOCKED` in execution state with a reason, and move to the next task.
- **Fix stacking**: If you have attempted 3+ fixes on the same failure without resolution, STOP. Mark the task as BLOCKED, record all attempted fixes and observations in execution state, and surface to the user.

## Rules
- Always check `execution-state.md` first for resume capability
- Never skip verification checks — fix failures before committing
- One commit per task — do not batch multiple tasks into one commit
- Cross-repo contracts in the plan are the source of truth for shared interfaces
- If a task requires clarification, mark it as blocked rather than guessing
- Update `execution-state.md` after every significant event (commit, failure, block)
