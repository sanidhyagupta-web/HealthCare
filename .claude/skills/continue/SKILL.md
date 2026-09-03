---
name: continue
description: Resume the most recent implementation workflow
disable-model-invocation: true
allowed-tools:
  - Read
  - Glob
---

# Resume Workflow: /continue

Find the most recent in-progress workflow and help the user resume it.

## Steps

1. Search for all execution state files:
   ```
   Glob: docs/execution/*/execution-state.md
   ```

2. If no execution state files found:
   > No active workflows found. Start a new one with `/implement <ticket-id>`.

   Stop.

3. If one or more found, read each `execution-state.md` and find the one that is NOT in
   `DONE` phase (i.e., still in progress). If multiple are in progress, pick the most
   recently modified one.

4. Extract the ticket ID from the `# Execution State: {TICKET_ID}` header.

5. Extract the current `**Phase**` value.

6. Tell the user:
   > **Active workflow found**: {TICKET_ID}
   > **Current phase**: {PHASE}
   > **Execution folder**: {EXEC_FOLDER}
   >
   > To resume, run: `/implement {TICKET_ID}`

   Stop.
