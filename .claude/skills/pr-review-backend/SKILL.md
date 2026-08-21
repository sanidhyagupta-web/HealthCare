---
name: pr-review-backend
description: Review a backend pull request with full context gathering, rule-based analysis, and inline comment posting.
disable-model-invocation: true
argument-hint: <pr-url-or-number>
allowed-tools:
  - Read
  - Write
  - Edit
  - Glob
  - Grep
  - Bash
  - Agent
  - AskUserQuestion
  # <!-- CUSTOMIZE: Add your ticket tracking MCP tools here, e.g.: -->
  # - mcp__linear__get_issue
  # - mcp__linear__list_issues
---

# Review Backend Pull Request

Full-workflow review for the backend repository with context gathering, configurable rules, severity-based analysis, user checkpoint, and inline comment posting.

---

## 1. Input Parsing

PR reference: `$ARGUMENTS`

If empty, ask the user for the PR number or URL.

Parse the PR reference to extract:
- `OWNER` / `REPO` / `PR_NUMBER` from URL (e.g., `https://github.com/OWNER/REPO/pull/123`)
- If only a number is given, default to the backend repo <!-- CUSTOMIZE: your default backend repo name and org -->

---

## 2. Context Gathering

Gather all context before analysis. Display a progress checklist as you go.

### 2a. PR Metadata
```bash
gh pr view $PR_NUMBER --repo $OWNER/$REPO --json title,body,headRefName,baseRefName,commits,files,labels,author
```

### 2b. Full Diff
```bash
gh pr diff $PR_NUMBER --repo $OWNER/$REPO
```

### 2c. Ticket Context (if available)
<!-- CUSTOMIZE: Replace ticket ID pattern with your project's pattern, e.g., PROJ-\d+ -->
- Extract ticket ID from PR title, branch name, or body (pattern: `TICKET-\d+`)
- If a ticket tracking MCP is available, fetch ticket details <!-- CUSTOMIZE: e.g., via mcp__linear__get_issue -->
- Check for execution artifacts: `Glob: docs/execution/{TICKET_ID}-*/requirements.md`
- Also load `implementation-plan.md` and `execution-state.md` from the same execution directory if present (these are gitignored — only available during self-review when the reviewer is also the implementer)

**Degraded-mode handling:**
- **No ticket ID found** → Warn the user that no ticket could be identified. Skip acceptance criteria checking and proceed with a code-quality-only review.
- **Ticket found but no acceptance criteria** → Warn the user. Note that the completeness check will be limited to code-level analysis only.
- **No execution artifacts found** → Note this and proceed normally. Execution artifacts are optional context.

### 2d. Load Conventions
Read the following for project conventions:
<!-- CUSTOMIZE: Paths to your repo's CLAUDE.md files -->
- Root `CLAUDE.md`
- `CLAUDE.md` (if accessible)

### 2e. Load Review Rules
Read these rule files — they define what to check and at what severity:
<!-- CUSTOMIZE: Adjust rule file list to match your project -->
- `.claude/rules/backend-lang.md` — architecture, DTOs, security, code quality
- `.claude/rules/backend-migrations.md` — migration conventions
- `.claude/rules/backend-testing.md` — integration test patterns
- `.claude/rules/security.md` — auth, input validation, SQL injection, secrets, XSS
- `.claude/rules/general-quality.md` — error handling, logging, naming, dead code, API contracts
- `.claude/rules/testing-standards.md` — test coverage, unhappy paths, assertions

Each rule section has a `<!-- severity: ... -->` marker. Use these to categorize findings.

---

## 3. Analysis

For each changed file in the diff:

1. **Read the full file** (not just the diff) to understand context
2. **Apply all applicable rules** from the loaded rule files
3. **Check acceptance criteria** coverage if a ticket was found
4. **Categorize each finding** using the severity from the rule:

| Icon | Level | Meaning | Maps from rule severity |
|------|-------|---------|------------------------|
| :red_circle: | **Blocker** | Must fix before merge | `blocker` |
| :yellow_circle: | **Suggestion** | Should fix, non-blocking | `suggestion` |
| :green_circle: | **Nit** | Minor style/preference | `nit` |
| :speech_balloon: | **Question** | Needs clarification | (reviewer judgment) |
| :clap: | **Praise** | Good pattern worth noting | (reviewer judgment) |

### Completeness Check

After rule-based analysis, perform a dedicated completeness sweep:

- **Acceptance criteria coverage** — If ticket context with acceptance criteria is available, produce a table mapping each criterion to its status:

  | Criterion | Status | Notes |
  |-----------|--------|-------|
  | *criterion text* | Addressed / Partial / Missing | *brief explanation* |

  If no acceptance criteria are available, skip this table and note why (no ticket found, or ticket had no criteria).

- **Missing tests** — Flag new code paths (service methods, controllers, utilities) that lack corresponding test coverage.
- **Missing migrations/config** — Flag new entity fields, tables, or relationships referenced in code without corresponding migrations. Flag new environment variables or config properties used without being defined in config files.
- **Cross-repo notes** — If the PR changes API response/request shapes, add an informational note that frontend consumers may need corresponding updates.

### Quick-Reference Checklist

<!-- CUSTOMIZE: Replace checklist items with your backend's conventions -->
Use this as a sweep after rule-based analysis to catch anything the rules might miss:

- [ ] Follows established layered architecture pattern
- [ ] Authorization on new endpoints
- [ ] Transactions on multi-write service methods
- [ ] DTOs used (entities never returned from controllers)
- [ ] Migrations follow naming conventions, no modification of existing migrations
- [ ] Integration tests cover new endpoints with real database
- [ ] No hardcoded secrets, no SQL injection, input validation present
- [ ] Null safety handled (no unchecked access)
- [ ] No N+1 query patterns
- [ ] Formatting applied, commit messages follow project format

---

## 4. User Checkpoint

Present a summary of findings organized by severity:

```
## Review Summary for PR #<number>: <title>

### Completeness Check
<acceptance criteria table if available, or note explaining why it was skipped>
<missing tests, missing migrations/config, cross-repo notes — if any>

### Findings
- :red_circle: Blockers: <count>
- :yellow_circle: Suggestions: <count>
- :green_circle: Nits: <count>
- :speech_balloon: Questions: <count>
- :clap: Praise: <count>

### Details
<list each finding with file, line, severity icon, rule reference, and description>
```

Then ask the user with AskUserQuestion:
- **"Post review"** — post inline comments and submit review
- **"Let me review first"** — show full details, let user edit before posting
- **"Cancel"** — stop without posting

If "Let me review first", wait for user to say proceed. If "Cancel", stop.

---

## 5. Post Inline Comments

For each finding that maps to a specific file and line:

```bash
gh api repos/{OWNER}/{REPO}/pulls/{PR_NUMBER}/reviews \
  --method POST \
  --field body="<summary>" \
  --field event="<APPROVE|COMMENT|REQUEST_CHANGES>" \
  --field 'comments[][path]=<file>' \
  --field 'comments[][position]=<diff-position>' \
  --field 'comments[][body]=<icon> <message>'
```

> **Tip:** `position` is the 1-indexed line offset within the diff hunk (from the `@@` line). If position calculation proves unreliable, use the newer API fields: `subject_type: "line"`, `line`, and `side: "RIGHT"`.

### Error Handling

- **Line not in diff** → Do not attempt to post as an inline comment. Instead, include the finding in the review body summary.
- **Auth error (401/403)** → Inform the user to run `gh auth login` and retry.
- **PR closed or merged** → Warn the user. Offer to post findings as a regular issue comment instead.
- **General API failure** → Display the full findings summary to the user so review work is not lost. Include the error details so the user can debug.

### Determine review action:
- If any :red_circle: Blockers → `REQUEST_CHANGES`
- If only :yellow_circle: Suggestions or lower → `COMMENT`
- If only :clap: Praise and :green_circle: Nits → `APPROVE`

### Comment format (terse, one-line per finding):
```
:red_circle: [BE-03] Missing authorization on new endpoint
:yellow_circle: [GEN-08] Potential NPE — Optional.get() without isPresent check
:green_circle: [GEN-03] Consider renaming `proc` to `processor` for clarity
:clap: Clean separation of concerns in the service layer
```

Use the rule ID (e.g., SEC-01, GEN-08, BE-02) in the comment for traceability.

---

## 6. Report

After posting, summarize to the user:

```
## Review Posted

- **Action**: REQUEST_CHANGES / COMMENT / APPROVE
- **Findings**: X blockers, Y suggestions, Z nits, W questions
- **PR**: <URL>

<any additional notes or recommendations>
```
