---
name: implement
description: Implement a ticket end-to-end through the AI development workflow
argument-hint: <ticket-id>
disable-model-invocation: true
allowed-tools:
  - Read
  - Write
  - Edit
  - Glob
  - Grep
  - Bash
  - Task
  - AskUserQuestion
---

# Workflow Orchestrator: /implement

You are an orchestrator that drives the AI development workflow end-to-end for a ticket.
Your job is to execute the workflow phases in order, pausing only where human input is needed,
and resuming from where you left off — even across session restarts.

---

## 1. Input Parsing

The ticket ID is: `$ARGUMENTS`

If `$ARGUMENTS` is empty or missing, respond with:

> **Usage**: `/implement <ticket-id>`
>
> Example: `/implement PROJ-123`
>
> This command drives the full AI development workflow for a ticket:
> requirements, clarifications, planning, implementation, checks, and PRs.
>
> To resume the most recent workflow, use `/continue`.

Then stop — do not proceed further.

Set `TICKET_ID` to the value of `$ARGUMENTS`.

---

## 2. State Resolution

Determine whether this is a fresh start or a resume by looking for existing execution state.

### 2a. Find existing execution folder

Search for a folder matching the ticket ID:

```
Glob: docs/execution/{TICKET_ID}-*/execution-state.md
```

### 2b. If execution state exists — RESUME

Read `execution-state.md`. Extract the current value of the `**Phase**` field.
This is where the workflow left off. The `EXEC_FOLDER` is the parent directory of the found file.

Tell the user:

> Resuming workflow for **{TICKET_ID}** from phase: **{PHASE}**

Then jump directly to that phase in the dispatch table below.

### 2c. If no execution state exists — FRESH START

Set `PHASE` to `REQUIREMENTS`. Proceed to phase dispatch.

---

## 3. Phase Dispatch

Execute phases in order. After completing each phase, update the `**Phase**` field in
`execution-state.md` to the NEXT phase before either continuing or stopping.

### Phase Table

| Phase | Skill | Auto-continue? |
|-------|-------|----------------|
| `REQUIREMENTS` | requirements | No — stop for clarifications |
| `CLARIFICATIONS` | clarifications | No — stop if new questions |
| `PLANNING` | plan | No — stop for plan review |
| `PLAN_REVIEW` | *(await approval)* | No — stop for approval |
| `EXECUTION_SETUP` | execution-setup | Yes |
| `IMPLEMENTATION` | implement-code | Yes — flows into checks |
| `POST_CHECKS` | post-checks | No — stop for review |
| `USER_REVIEW` | *(await approval)* | No — stop for approval |
| `UPDATE_CLAUDE_MD` | update-claude-md | Yes |
| `CREATE_PRS` | create-prs | Yes — flows into registry |
| `UPDATE_FEATURE_REGISTRY` | update-feature-registry | Terminal — done |

---

### REQUIREMENTS Phase

**Goal**: Read the ticket and produce requirements + clarifications documents.

1. Follow the `requirements` skill instructions:
   - Read the ticket via MCP (or ask user to paste content)
   - Create the execution folder: `docs/execution/{TICKET_ID}-{kebab-summary}/`
   - Generate `requirements.md` and `clarifications.md`

2. Create `execution-state.md` in the execution folder with initial state:
   ```markdown
   # Execution State: {TICKET_ID}

   **Phase**: REQUIREMENTS
   **Status**: NOT_STARTED
   **Base Branch**: (to be set)

   ## Branches
   - BE: (not set)
   - FE: (not set)
   - Ops: (not set)

   ## Tasks
   (populated during EXECUTION_SETUP phase)

   ## Log
   | Timestamp | Event | Details |
   |-----------|-------|---------|
   | {now ISO} | Workflow started | Phase: REQUIREMENTS |
   ```

3. Update `**Phase**` to `CLARIFICATIONS`.

4. **STOP**. Tell the user:
   > Requirements and clarifications generated.
   >
   > **Next**: Review `clarifications.md`, fill in your answers, then run `/implement {TICKET_ID}` to continue.

---

### CLARIFICATIONS Phase

**Goal**: Process user answers to clarifications and update requirements.

1. Read `{EXEC_FOLDER}/clarifications.md`.

2. If status is already `RESOLVED` with no new questions: skip to PLANNING phase. Update `**Phase**` to `PLANNING` and auto-continue.

3. If answers are still blank: **STOP** — tell user to fill in clarifications.

4. Follow the `clarifications` skill instructions to update requirements.

5. After processing:
   - If new clarifications added (status = `PARTIAL`): keep phase as `CLARIFICATIONS`. **STOP**.
   - If all resolved: update `**Phase**` to `PLANNING`. **STOP** — tell user to run `/implement {TICKET_ID}`.

---

### PLANNING Phase

**Goal**: Convert requirements into an implementation plan.

1. Follow the `plan` skill instructions:
   - Read finalized requirements
   - Explore codebase
   - Create `implementation-plan.md`

2. Update `**Phase**` to `PLAN_REVIEW`.

3. **STOP** — tell user to review the plan.

---

### PLAN_REVIEW Phase

**Goal**: Get user approval of the implementation plan.

1. Ask the user with AskUserQuestion:
   - "Yes, proceed with implementation"
   - "I've made edits — re-read the plan and proceed"
   - "No, I need more time"

2. If "No": **STOP**.

3. If "Yes" or edits: update `**Phase**` to `EXECUTION_SETUP`. **Auto-continue**.

---

### EXECUTION_SETUP Phase

**Goal**: Set up execution tracking.

1. Follow the `execution-setup` skill instructions.

2. Update `**Phase**` to `IMPLEMENTATION`. **Auto-continue**.

---

### IMPLEMENTATION Phase

**Goal**: Implement all tasks from the plan.

1. Get base branch (if not set): ask user.

2. Follow the `implement-code` skill instructions:
   - Create branches
   - Launch agents per repository (use `backend-implementer` and `frontend-implementer` custom agents)
   - Each agent implements tasks sequentially with verification

3. Update `**Phase**` to `POST_CHECKS`. **Auto-continue**.

---

### POST_CHECKS Phase

**Goal**: Run verification checks.

1. Follow the `post-checks` skill instructions.

2. Update `**Phase**` to `USER_REVIEW`.

3. **STOP** — tell user to review code and check results.

---

### USER_REVIEW Phase

**Goal**: Get user approval.

1. Ask with AskUserQuestion:
   - "Yes, looks good — proceed to finalize"
   - "There are issues — I'll describe them"
   - "No, I need more time"

2. If "No": **STOP**. If issues: **STOP** and ask for details.

3. If "Yes": update `**Phase**` to `UPDATE_CLAUDE_MD`. **Auto-continue**.

---

### UPDATE_CLAUDE_MD Phase

**Goal**: Update documentation.

1. Follow the `update-claude-md` skill instructions.

2. Update `**Phase**` to `CREATE_PRS`. **Auto-continue**.

---

### CREATE_PRS Phase

**Goal**: Push and create PRs.

1. Follow the `create-prs` skill instructions.

2. Update `**Phase**` to `UPDATE_FEATURE_REGISTRY`. **Auto-continue**.

---

### UPDATE_FEATURE_REGISTRY Phase

**Goal**: Update the feature registry with everything added or changed in this ticket.

1. Follow the `update-feature-registry` skill instructions.

2. Update `**Phase**` to `DONE` and `**Status**` to `COMPLETE`.

3. Tell the user workflow is complete. List all PR URLs.

---

## 4. Execution State Updates

Every phase transition, add a log entry:
```markdown
| {ISO timestamp} | Phase transition | {OLD_PHASE} -> {NEW_PHASE} |
```

## 5. Error Handling

If any phase fails:
1. Log the error in `execution-state.md`
2. Do NOT advance the phase
3. Tell the user what went wrong
4. User can fix and run `/implement {TICKET_ID}` to retry
