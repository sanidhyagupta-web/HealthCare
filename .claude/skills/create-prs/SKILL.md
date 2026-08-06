---
name: create-prs
description: Push feature branches to remote and create pull requests for each affected repository.
disable-model-invocation: true
---

# Push & Create Pull Requests

Push feature branches and create PRs for each affected repository.

## Prerequisites
- All tasks complete, checks pass, user approved, CLAUDE.md updated

## Steps

### 1. Read State
Read `execution-state.md` for branch names and task list.

### 2. Push Branches
For each affected repository:
```bash
cd {repo-path}
git push -u origin {branch-name}
```

### 3. Create Pull Requests
For each affected repository:
```bash
gh pr create --title "{TICKET-ID}: {Short summary}" --body "$(cat <<'EOF'
## Summary
- {2-4 bullet points}

## Changes
### {Service/App name}
- {Key files and what changed}

## Testing
- {Tests run and results}
- {Manual verification steps}

## References
- **Ticket**: {ticket ID}
- **Requirements**: docs/execution/{ticket}/requirements.md
- **Implementation Plan**: docs/execution/{ticket}/implementation-plan.md
- **Execution State**: docs/execution/{ticket}/execution-state.md

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

### 4. Link to Ticket Tracker (if available)
If a ticket tracking MCP tool is available (e.g., Linear, Jira, GitHub Issues), attach the PR URLs to the ticket:
- For Linear: use `mcp__linear__save_issue` to add the PR URL as an attachment or comment
- For Jira: use the Jira MCP to post a comment with the PR URLs
- If no MCP is available, remind the user to manually link the PR to the ticket

### 5. Update Execution State
Set status to `PR_CREATED`. Record PR URLs.

### 6. Report
Provide PR links, summary of each PR, and next steps.

## Rules
- Always push with `-u` flag
- Do NOT force push
- One PR per repository with changes
- PR title follows the repo's commit format
- Do not merge — that's a manual step
