---
name: execution-setup
description: Set up execution tracking from an approved implementation plan. Creates the execution state checklist.
disable-model-invocation: true
---

# Setup Execution Tracking

After the user has approved the implementation plan, set up execution tracking artifacts.

## Steps

1. **Create `execution-state.md`** in the execution folder from the task list in `implementation-plan.md`:

```markdown
# Execution State: {TICKET-ID}

**Phase**: EXECUTION_SETUP
**Status**: NOT_STARTED
**Base Branch**: {to be set}

## Branches
- BE: {to be set}
- FE: {to be set}
- Ops: {to be set}

## Tasks
- [ ] 1. [BE] {Task description}
- [ ] 2. [BE] {Task description}
- [ ] 3. [FE] {Task description}
...

## Log
| Timestamp | Event | Details |
|-----------|-------|---------|
| | | |
```

2. **If a ticket system MCP is available**:
   - Create subtasks for each task in the plan
   - Record ticket IDs in `execution-state.md`

3. **Confirm** setup is complete and user can proceed.
