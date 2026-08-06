---
name: update-feature-registry
description: Update docs/features/ after a ticket is completed. Updates or creates the relevant per-feature index.md files and keeps the master index in sync so future planning can identify what might break.
disable-model-invocation: true
allowed-tools:
  - Read
  - Write
  - Edit
  - Glob
  - Grep
  - Bash
---

# Update Feature Registry

Update `docs/features/` with everything that was added or changed in this ticket.
The master index (`docs/features/index.md`) and individual feature files are read automatically during `/plan`.

## Prerequisites
- All tasks complete, PRs created, `execution-state.md` has PR URLs recorded

---

## 1. Read Execution Context

Read:
- `execution-state.md` — ticket ID, PR URLs, branch names, completed tasks
- `implementation-plan.md` — cross-repo contracts, task list, what was built

---

## 2. Fetch PR Diffs

For each PR URL in `execution-state.md`:

```bash
gh pr view {PR_NUMBER} --repo {OWNER}/{REPO} --json title,url,number,baseRefName
gh pr diff {PR_NUMBER} --repo {OWNER}/{REPO}
```

---

## 3. Load the Feature Registry

Read `docs/features/index.md` (master index).
Then read the individual feature files that are likely affected by this ticket.

Feature files live at: `docs/features/{feature-name}/index.md`

Discover current features dynamically:
```bash
ls docs/features/
```

Use the Workflow Routing Rules table in `docs/features/index.md` to match changed files to feature names, then load only those feature files.

---

## 4. Analyze the Diffs

For each changed file, identify what category it falls into:

### Services & Business Rules
- **New service**: A new service directory was added → create a new feature file
- **New entity/resource**: A new DB table or domain model was added → update the owning service file
- **Changed business rules**: Handler or service logic that enforces a constraint was added or modified → update the relevant service file
- **New inter-service dependency**: A service now calls another → update both files

### Backend APIs
- **New endpoints**: New handler registrations, new routes in `serverless.yml` → update the owning service file
- **Modified endpoints**: Changed request fields, response fields, renamed fields → update the owning service file
- For each endpoint extract: HTTP method, path, request field names + types, response field names + types

### Frontend Features
- **New features**: New pages, significant new components or user flows → create or update the relevant frontend feature file
- **Enhanced features**: Existing pages with new capabilities → update the relevant frontend feature file
- For each: key file paths, which API endpoints it calls

### Consumer Mapping
For each modified backend API, search the frontend codebase for callers:
```bash
grep -r "{endpoint-path}" {frontend} --include="*.ts" --include="*.tsx" -l
```

For each modified shared utility, search for importers:
```bash
grep -r "{utility-name}" {backend} --include="*.ts" -l
```

> `{frontend}` and `{backend}` are the paths configured in your project's CLAUDE.md (e.g., `frontend/`, `backend/services/`). Adapt the glob patterns to match your project's actual directory structure.

---

## 5. Propose Updates

Present a summary before writing:

```
## Feature Registry Updates for {TICKET-ID}

### Feature files to update:
- [UPDATED] {feature-name} — added {endpoint/rule}, updated {section}
- [UPDATED] {frontend-feature} — new {flow/component}

### Feature files to create (new features):
- [NEW] {feature-name} — one-line description

### Master index changes:
- Add row for {new-feature} to the relevant table

### Consumers discovered:
- {METHOD} /{path} called by: {frontend-file}
```

Ask the user to confirm or adjust before writing.

---

## 6. Write Updates

### Updating an existing feature file (`docs/features/{feature}/index.md`):

- **API endpoints table**: Add new rows, update changed rows, mark removed endpoints with ~~strikethrough~~ `(removed in {TICKET-ID})`
- **Business rules**: Add new rules. Never remove old ones — if a rule was removed, mark it: `~~rule text~~ (removed in {TICKET-ID})`
- **Safe vs Dangerous Changes**: If a new dangerous change pattern was discovered, add a row to the Dangerous table. If a change was escalated to human review, add it to Human Escalation Required
- **Forbidden Patterns**: If a new anti-pattern was introduced or caught in review, add a bullet
- **Key files**: Add newly introduced files
- **Context Routing — Optional**: If a new conditional dependency was introduced, add a row to the Optional table in the individual feature file
- **Dependency graph in `docs/features/index.md`**: If a new hard dependency was introduced (new direct import, new shared schema, new Lambda invocation), update the **Mandatory Dependencies** table; if a new consumer was discovered, update the **Downstream Impact** table
- Update `Last updated` at the top with the ticket ID

### Creating a new feature file:

Create `docs/features/{feature-name}/index.md` — **stay ≤ 400 lines**.

**Template tiers when tight on budget (omit in this order):**
- Optional: Status/State Machine, External Integrations, Architectural Decisions
- Recommended: Entities Owned, Access Control, Forbidden Patterns, Testing Expectations, Known Error Scenarios
- Required (never omit): Domain Purpose, Invariants, Business Rules, Safe vs Dangerous Changes, Key Files, Context Routing

Use the appropriate template below.

**For backend services:**

```markdown
---
feature: {service-name}
type: backend-service
domain: {domain}
criticality: high|medium|low
depends_on: [shared-backend, {other}]
consumed_by: [{frontend-feature}]
tags: [{domain-tag}]
---

# {Service Name}

## Overview
| Field | Value |
|-------|-------|
| **Type** | Backend Service |
| **Path** | `{backend}/services/{service-name}/` |
| **Domain** | {domain} |
| **Last updated** | {TICKET-ID} — [{PR title}]({PR URL}) |

## Domain Purpose
{1-2 sentences: what business problem this service solves. NO file paths, handler names, or library names.}

## Entities Owned
| Entity | Description | Key Fields |
|--------|-------------|------------|
| `{table}` | {what} | `id`, `status` |

## Status / State Machine
| Status | Business Meaning | Can Transition To | Trigger |
|--------|-----------------|-------------------|---------|
| `STATUS_A` | {meaning} | `STATUS_B` | {trigger} |

**Rules**: {transition constraints}

## Invariants
- {hard constraint — AI must never violate}

## Access Control

**Model**: {RBAC | API-key | Ownership | N/A} — role/auth definitions in `.claude/rules/security.md`

| Endpoint / Action | Access Condition | Enforced In |
|-------------------|-----------------|-------------|
| {action} | {condition} | {where} |

## Business Rules

Severity: `CRITICAL` | `HIGH` | `MEDIUM` | `LOW`

| # | Rule | Enforced In | Severity |
|---|------|-------------|----------|
| BR-01 | {rule} | `src/services/x.ts` | CRITICAL |

## External Integrations
| System | Trigger | What Happens |
|--------|---------|--------------|
| {system} | {event} | {result} |

## API Endpoints
| Method | Path | Auth | Who Uses It | Description |
|--------|------|------|-------------|-------------|
| `GET` | `/path` | required | `frontend-x` | {description} |

## Safe vs Dangerous Changes

### Safe
- {e.g., adding optional response fields}

### Dangerous — Requires Review
| Change | Risk | Why |
|--------|------|-----|
| {change} | CRITICAL | {reason} |

### Human Escalation Required
- {e.g., schema migration that transforms existing data}

## Known Error Scenarios
| Scenario | Error Returned | Root Cause |
|----------|---------------|------------|
| {scenario} | `400 CODE` | {why} |

## Testing Expectations
**Required**: {test types}
**Critical assertions**: {key things tests must verify}

## Architectural Decisions
| Decision | Reason | Do Not Change Without |
|----------|--------|-----------------------|
| {decision} | {reason} | {impact} |

## Forbidden Patterns
- Never {anti-pattern} — {reason}

## Key Files
- `src/handlers/x.ts` — route definitions
- `src/services/x.ts` — business logic + rules

## Context Routing

### Optional
| Feature | Load when |
|---------|-----------|
| `{feature}` | {condition} |

### Workflow Loading Map
| Workflow | Sections to load |
|----------|-----------------|
| `/plan` | Full file — dependency graph in `docs/features/index.md` |
| `/implement-code` | Invariants + Business Rules + Key Files |
| `/pr-review` | Invariants + Business Rules + Change Risk Areas |
| `/requirements` | Domain Purpose + Invariants + Access Control + State Machine |

## Rules
- Never remove existing entries — only add or update. Mark removed things with strikethrough
- If a consumer cannot be confirmed, mark it `(unverified)` rather than omitting it
- Keep API request/response shapes at field name + type level — no implementation code
- One file per feature: `docs/features/{feature-name}/index.md`
- When adding a new feature file, also update the Mandatory Dependencies and Downstream Impact tables in `docs/features/index.md`
