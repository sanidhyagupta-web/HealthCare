---
name: init-feature-registry
description: One-time full codebase scan to bootstrap docs/features/ from scratch. Run once when adopting this workflow on an existing project. Generates per-feature index files and a master index for all backend services, frontend features, and shared libraries. Also writes the equivalent human-readable content into code-wiki/{project-id}/ (Architecture/Overview.md, per-feature Index.md files, Schemas/schemas.md), committed to the shared wiki/init-scaffold branch/PR.
disable-model-invocation: true
allowed-tools:
  - Read
  - Write
  - Glob
  - Grep
  - Bash
---

# Init Feature Registry

Bootstrap `docs/features/` by scanning the entire codebase. This is a one-time setup skill. After this runs, use `/update-feature-registry` to keep it current ticket-by-ticket.

> **What you are creating**: AI-readable engineering context contracts — not documentation.
> Each feature file defines the business rules, invariants, and risk boundaries the AI must respect
> when modifying that feature. Write for the agent making changes, not for a human reading a wiki.

## Template Tiers
When a file is tight on the 400-line budget, omit sections in this order:
- **Optional** (omit first): Status/State Machine, External Integrations, Architectural Decisions
- **Recommended** (omit only if forced): Entities Owned, User Roles, Forbidden Patterns, Testing Expectations, Known Error Scenarios
- **Required** (never omit): Domain Purpose, Invariants, Business Rules, Safe vs Dangerous Changes, Key Files, Context Routing

## When to Run

**One time per project.** Run this once when first adopting this workflow. It is not a recurring command.

| Situation | Action |
|-----------|--------|
| `docs/features/` is empty or missing | ✅ Run this skill |
| After a major refactor that made the registry significantly stale | ✅ Delete `docs/features/` and re-run |
| `docs/features/` already has files | ❌ Stop — use `/update-feature-registry` instead |
| After finishing any ticket | ❌ Stop — use `/update-feature-registry` instead |

> **Guard**: Before doing anything else, check whether `docs/features/` already contains files. If it does, stop and tell the user to use `/update-feature-registry`.

## Why Run This

Without the feature registry, `/plan` produces generic implementation plans with no awareness of what existing code a ticket might break. With it:

- **`/plan`** reads `docs/features/index.md` and generates an **Impact Analysis** — a table of which services, endpoints, and frontend features the ticket touches and what the downstream risk is
- **`/pr-review-backend` and `/pr-review-frontend`** cross-check PRs against the registry and flag unupdated consumers as blockers
- **`/implement-code`** loads only the relevant feature files as context, so the agent knows the invariants and forbidden patterns before touching anything

This full scan runs once because it reads every handler, service, DTO, and Redux slice in the codebase — it's expensive by design. After bootstrap, `/update-feature-registry` maintains it incrementally at the end of each ticket, touching only the files changed by that ticket.

The same scan also produces `code-wiki/{project-id}/` — the human-readable rendering of the same facts (system architecture, per-feature narrative pages, the shared schema catalog) for readers who aren't the AI. See Step 7b.

---

## 1. Check Registry State

```bash
find docs/features/ -maxdepth 2 -name "*.md" 2>/dev/null | head -5
```

If `.md` files already exist in `docs/features/`, tell the user and stop. The registry is already bootstrapped — use `/update-feature-registry` to keep it current. (`.gitkeep` and other non-markdown files do not count as registry content.)

---

## 2. Scan Backend Services

First, discover all service packages and detect their architecture:

```bash
# List top-level service directories
ls {backend}/services/

# Detect framework markers to identify architecture type
find {backend}/services -maxdepth 2 \( \
  -name "serverless.yml" \
  -o -name "pom.xml" \
  -o -name "build.gradle" \
  -o -name "pyproject.toml" \
  -o -name "manage.py" \
\) -not -path "*/node_modules/*" -not -path "*/dist/*" 2>/dev/null
```

**Architecture detection**: Identify the framework pattern before reading service code:
- **Serverless (Lambda/FaaS)**: `serverless.yml` present — service maps to Lambda functions grouped by HTTP events
- **Spring Boot / Java**: `pom.xml` or `build.gradle` — controllers under `src/main/java/**/controller/`
- **Node.js / Express / Fastify / NestJS**: `package.json` with no `serverless.yml` — routes in `src/routes/`, `src/controllers/`, or module folders
- **Python / FastAPI / Django**: `pyproject.toml` or `manage.py` — routes in `views/`, `routers/`, or `endpoints/`

**Companion package detection**: Some features span two directories (e.g., `resources/` provides the HTTP API layer while `resource-integrations/` provides the handler implementations). When two service directories share a domain (same nouns in directory names, cross-imports between them), document them as **one feature file** covering both packages.

For each service directory (or companion-package pair) found:

### 2a. Read service entry points (adapt to architecture)

**Serverless (Lambda) projects:**
```bash
cat {backend}/services/{service}/serverless.yml
cat {backend}/services/{companion-package}/serverless.yml 2>/dev/null
```
Extract: HTTP event definitions (`http:` blocks) → method, path, authorizer; environment variables; service name.

**Spring Boot / Java projects:**
```bash
cat {backend}/services/{service}/src/main/resources/application.yml 2>/dev/null
grep -rn "@RequestMapping\|@GetMapping\|@PostMapping\|@PutMapping\|@DeleteMapping\|@PatchMapping" {backend}/services/{service}/src --include="*.java" | head -30
```
Extract: context path, route annotations → method + path; `spring.security.*` for auth config.

**Node.js / Express / Fastify / NestJS projects:**
```bash
cat {backend}/services/{service}/src/app.ts 2>/dev/null || cat {backend}/services/{service}/src/index.ts 2>/dev/null
find {backend}/services/{service}/src -name "*.ts" -o -name "*.js" | xargs grep -l "router\.\|app\.\(get\|post\|put\|delete\|patch\)\|@Controller\|@Module" 2>/dev/null | head -10
```
Extract: route registrations or controller decorators → method + path; auth middleware or guards at router level.

### 2b. Read handler / controller files

Adapt the search pattern to the project structure:

```bash
# Serverless / Node.js handler pattern
find {backend}/services/{service}/src -type f \( -name "*.ts" -o -name "*.js" \) \
  \( -path "*/handlers/*" -o -name "*handler*.ts" -o -name "handler-factory.ts" \) \
  2>/dev/null | grep -v "node_modules\|dist\|\.d\.ts\|__tests__"

# Controller / service / repository pattern (Spring Boot, NestJS, Laravel, etc.)
find {backend}/services/{service}/src -type f \
  \( -path "*/controller*/*" -o -path "*/controllers/*" \
     -o -name "*Controller*" -o -name "*controller*" \) \
  2>/dev/null | grep -v "node_modules\|dist\|__tests__\|target"

# Module pattern — controller and routes live under each feature module folder
# e.g., src/modules/admin/controller.ts + src/modules/admin/routes.ts
# Covers both prefixed names (admin.controller.ts) and generic names (controller.ts)
find {backend}/services/{service}/src/modules -type f \
  \( -name "controller.ts" -o -name "controller.js" \
     -o -name "routes.ts" -o -name "routes.js" \
     -o -name "*.controller.*" -o -name "*.routes.*" \) \
  2>/dev/null | grep -v "node_modules\|dist"
```

For each handler/controller file found, read it and extract:
- Route registrations or HTTP method annotations (method + path)
- Auth patterns (guards, middleware, JWT validators, public route markers)
- Request/response shapes or DTOs referenced
- Routing / dispatch logic (e.g., factory patterns, module-level routing)

### 2c. Read service files — deep scan
```bash
# Flat services/ folder (serverless, layered architecture)
find {backend}/services/{service}/src -name "*.ts" -path "*/services/*" 2>/dev/null | grep -v "node_modules\|dist\|\.d\.ts\|__tests__"

# Module pattern — service.ts lives inside each feature module folder
# e.g., src/modules/admin/service.ts, src/modules/auth/service.ts
find {backend}/services/{service}/src/modules -type f \
  \( -name "service.ts" -o -name "service.js" -o -name "*.service.*" \) \
  2>/dev/null | grep -v "node_modules\|dist\|__tests__"

# Also read repository files in module pattern — these hold data-access logic and DB queries
find {backend}/services/{service}/src/modules -type f \
  \( -name "repository.ts" -o -name "repository.js" -o -name "*.repository.*" \) \
  2>/dev/null | grep -v "node_modules\|dist\|__tests__"
```
Read the **full content** of each service file (not just method signatures). Extract:
- Business rule guards — every `if` condition that throws, returns an error, or rejects a request
- History / audit clone patterns — any code that copies a record into a `_history` or `_audit` table
- In-memory cache patterns — module-level `Map`, object literals, or variables used as caches (note: these are process-scoped and lost on restart or scale-out; in serverless/FaaS environments they are also lost on cold start)
- Mode / flag patterns — any `automatic` vs `manual` branching, feature flag checks, CRT-style template conditionals
- Cross-service method calls — any other service class instantiated or injected (note the class name and what method is called)

### 2d. Read DTO / schema files
```bash
# Flat dto/ folder (layered architecture)
ls {backend}/services/{service}/src/dto/ 2>/dev/null

# Module pattern — schema.ts lives inside each feature module folder
# e.g., src/modules/admin/schema.ts (Zod, Drizzle, Joi, class-validator schemas)
find {backend}/services/{service}/src/modules -type f \
  \( -name "schema.ts" -o -name "schema.js" -o -name "*.dto.*" -o -name "*.schema.*" \) \
  2>/dev/null | grep -v "node_modules\|dist"
```
For each file, extract field names and types for request/response shapes and DB entity definitions.

### 2e. Read DB migrations for constraints
```bash
ls {backend}/services/shared/src/database/migrations/ 2>/dev/null || \
ls {backend}/services/{service}/migrations/ 2>/dev/null
```
Read the actual SQL migration files (not just list them). Extract:
- `CREATE UNIQUE INDEX` / `ADD CONSTRAINT ... UNIQUE` — uniqueness rules (note which migration version introduced them)
- `EXCLUDE USING gist` — exclusion constraints (overlap prevention, e.g., date range no-overlap)
- `CHECK (...)` — column-level check constraints
- `FOREIGN KEY` — referential integrity between tables

These constraints are authoritative business rules invisible in application code.

### 2f. Scan for cross-service imports

Adapt to the project's language:

```bash
# TypeScript / JavaScript
grep -rn "import.*from '.*services/" {backend}/services/{service}/src --include="*.ts" --include="*.js" 2>/dev/null | grep -v node_modules
grep -rn "import.*Service" {backend}/services/{service}/src --include="*.ts" 2>/dev/null | grep -v "from '\.\|from '\.\."

# Java / Spring — injected service dependencies
grep -rn "@Autowired\|@Inject\|new .*Service(" {backend}/services/{service}/src --include="*.java" 2>/dev/null | grep -v "node_modules\|target"

# Python
grep -rn "^from.*import\|^import " {backend}/services/{service} --include="*.py" 2>/dev/null | grep -i "service" | grep -v "__pycache__"
```

Direct compile-time or import-time dependencies between services are the **highest-risk couplings** in the system — a type or interface change in the imported service breaks the importer. Note every cross-service dependency found.

### 2g. Scan for inter-service calls and error patterns

```bash
# Lambda-to-Lambda invocations (AWS Serverless)
grep -rn "InvokeCommand\|lambda\.invoke\|LambdaClient" {backend}/services/{service}/src --include="*.ts" --include="*.js" 2>/dev/null | grep -v "node_modules\|dist"

# HTTP client calls to other services (Express, Spring Boot, FastAPI, etc.)
grep -rn "axios\.\|fetch(\|HttpClient\|RestTemplate\|requests\.get\|requests\.post\|httpx\." {backend}/services/{service}/src 2>/dev/null | grep -v "node_modules\|dist\|__tests__" | head -20

# Message queue / event bus publishing (SQS, SNS, EventBridge, Kafka, RabbitMQ)
grep -rn "putEvents\|sendMessage\|publish\|producer\.send\|channel\.publish" {backend}/services/{service}/src 2>/dev/null | grep -v "node_modules\|dist" | head -20

# Error throw / exception patterns for Known Error Scenarios
grep -rn "throw new\|createError\|raise.*Exception\|raise.*Error\|statusCode.*4[0-9][0-9]\|statusCode.*5[0-9][0-9]" {backend}/services/{service}/src 2>/dev/null | grep -v "node_modules\|dist\|__tests__" | head -30
```

Inter-service calls reveal runtime dependencies not visible in code imports. Error patterns populate the Known Error Scenarios table.

### 2h. Scan for security guard functions
```bash
# Sole enforcement points for access control — CRITICAL business rules
# CUSTOMIZE: replace these with your project's actual auth/guard function names
grep -rn "validateAccess\|checkPermission\|isAuthorized\|authGuard\|checkAccess\|extractAuthContext" {backend}/services/{service}/src --include="*.ts" 2>/dev/null | grep -v "node_modules\|\.d\.ts\|dist\|__tests__"
```
Any function that is the **sole enforcement point** for an access control rule is a CRITICAL business rule. Document it as:
`BR-XX | {functionName} guards {what it protects} | {file} (sole code path — never bypass or duplicate this guard) | CRITICAL`

This scan is required for every service — security guards are often invisible in route/framework config (serverless.yml, Spring Security, middleware chains) and easy to miss when reading only handler or controller code.

### 2i. Scan for async processes

```bash
# Scheduled jobs / cron expressions
grep -rn "cron\|@Scheduled\|schedule\|setInterval\|CronJob\|cronExpression" {backend}/services/{service}/src 2>/dev/null | grep -v "node_modules\|dist\|__tests__" | head -20

# Message queue consumers / event listeners
grep -rn "consumer\|subscribe\|@EventListener\|@KafkaListener\|@SqsListener\|channel\.consume\|queue\.process\|on('message" {backend}/services/{service}/src 2>/dev/null | grep -v "node_modules\|dist" | head -20

# Background workers / job queues (Bull, BullMQ, Celery, Sidekiq, etc.)
grep -rn "Worker\|@Process\|Queue\|\.add(\|\.process(\|celery\.task\|@shared_task" {backend}/services/{service}/src 2>/dev/null | grep -v "node_modules\|dist" | head -20

# Webhook handlers (inbound async triggers from external systems)
grep -rn "webhook\|Webhook" {backend}/services/{service}/src 2>/dev/null | grep -v "node_modules\|dist" | head -10
```

Async processes are invisible in HTTP route definitions but carry significant business logic. Document each one found:
- **Scheduled job**: what runs, at what interval, what data it reads/writes
- **Queue consumer**: which queue/topic, what it processes, what side effects it produces
- **Webhook listener**: which external system triggers it, what it does on receipt

Add these to the feature file's `External Integrations` table and flag relevant data shapes in `Safe vs Dangerous Changes` — changes to data these processes consume or produce can break silently with no HTTP error to catch them.

---

## 3. Scan Frontend Features

Identify major feature areas by reading the router config or pages directory:

```bash
ls {frontend}/apps/app/pages/ 2>/dev/null || ls {frontend}/apps/app/src/pages/ 2>/dev/null
ls {frontend}/apps/app/components/ 2>/dev/null
ls {frontend}/libs/ 2>/dev/null
```

For each significant feature area:

### 3a. Read Redux slices — full content
```bash
ls {frontend}/libs/redux/slices/ 2>/dev/null || ls {frontend}/apps/app/store/slices/ 2>/dev/null
```
**Read each slice file** (not just list them). For each slice extract:
- The state interface / type (what fields it holds)
- `initialState` shape
- All exported selector names (lines matching `export const select...` or `export const.*Selector`)
- Which feature domain the slice belongs to (from file name + state shape)

This is required to populate the `State (Redux)` section accurately — `ls` alone gives names, not meaning.

### 3b. Read service files
```bash
ls {frontend}/apps/app/services/ 2>/dev/null
```
For each service file, extract:
- Which API endpoints it calls (URL paths, methods)
- What data it sends/receives

### 3c. Read page and component files — UI states and flows
For the top-level feature pages, **read the component file** and look for:
- Conditional rendering based on status values (e.g., `status === 'TERMINATED'`, `isLoading`, `data.length === 0`) → these become **UI States**
- Threshold / warning conditions (e.g., `allocationPercentage > 100`, `status === 'ENDED'`, `status === 'ARCHIVED'`) → domain-specific UI states with business meaning
- Role-based conditional rendering (e.g., `role === 'admin'`, `hasPermission(...)`) → informs **Access Control**
- `useSelector(...)` calls → reveals which Redux slices the page consumes
- `dispatch(...)` calls → reveals which thunks / actions are triggered by user actions
- User-visible actions (button onClick handlers, form submit handlers) → these become **Key User Flows**

### 3d. Scan for auth utilities and shared hooks
```bash
grep -rn "useSelector\|createAuthHeaders\|UserRole\|RoleType" {frontend}/apps/app --include="*.ts" --include="*.tsx" -l 2>/dev/null | head -20
grep -rn "export.*enum.*Role\|export.*UserRole\|export.*RoleType" {frontend} --include="*.ts" 2>/dev/null
```
Identifies the frontend auth primitive (role enum location, auth header utility) for the `frontend-libs` feature file.

---

## 4. Discover Consumer Relationships

### 4a. Frontend → Backend (endpoint consumers)
For each backend API endpoint discovered in step 2, find which frontend files call it:
```bash
grep -r "{endpoint-path}" {frontend}/apps --include="*.ts" --include="*.tsx" -l 2>/dev/null
```

### 4b. Backend → Backend (cross-service direct imports)
Find all TypeScript direct imports between backend services — these are the highest-risk couplings:
```bash
grep -rn "import.*from '.*services/" {backend}/services --include="*.ts" 2>/dev/null | grep -v node_modules | grep -v "/shared/"
```
Each hit is a compile-time dependency. Note: `ServiceA imports ServiceB` means changing ServiceB's interface breaks ServiceA.

### 4c. Backend → Backend (runtime service calls)
Find all direct runtime calls from one service to another:
```bash
# Lambda-to-Lambda invocations (AWS Serverless)
grep -rn "InvokeCommand\|lambda\.invoke\|new LambdaClient" {backend}/services --include="*.ts" --include="*.js" 2>/dev/null | grep -v node_modules

# HTTP client calls between services (Express, Spring Boot, FastAPI, etc.)
grep -rn "axios\.\|fetch(\|HttpClient\|RestTemplate\|requests\.get\|requests\.post\|httpx\." {backend}/services 2>/dev/null | grep -v "node_modules\|dist\|__tests__" | head -30
```
These are runtime dependencies not visible in code imports or framework config.

### 4d. Backend → Backend (EventBridge publishers and consumers)
Find all EventBridge publish calls and their sources:
```bash
# CUSTOMIZE: replace the source prefix with your project's EventBridge source (e.g., "source.*your-app\.")
grep -rn "putEvents\|EventBridgeClient\|source.*your-app\." {backend}/services --include="*.ts" 2>/dev/null | grep -v node_modules
```
Publishers and consumers of the same event name are tightly coupled — a payload shape change breaks them simultaneously.

### 4e. Shared library consumers
For each shared utility exported from `{backend}/services/shared/src/`:
```bash
grep -r "{utility-name}" {backend}/services --include="*.ts" -l 2>/dev/null | grep -v "shared/src"
```

---

## 5. Propose the Registry Structure

Before writing any files, present a summary to the user:

```
## Feature Registry Bootstrap Plan

### Backend services to document ({N} features):
- {service-a} — {what it manages}
- {service-b} — {what it manages}
- ...

### Frontend features to document ({N} features):
- {feature-a} — {what the user does here}
- {feature-b} — {what the user does here}
- ...

### Shared libraries to document:
- shared-backend — Lambda Layer shared across all services

### Master index: docs/features/index.md

Ready to generate {N} feature files. Proceed?
```

Wait for user confirmation before writing.

---

## 5b. Collect Auth Model

**Goal**: know the roles/scopes/primitives before generating any Access Control sections.

First, check whether `.claude/rules/security.md` has the `Project Auth Model` section already filled in (no `{placeholder}` values):

```bash
grep -A 15 "## Project Auth Model" .claude/rules/security.md 2>/dev/null
```

**If populated** — use those values. Skip the questions below.

**If not populated or file missing** — ask the user:

> **Before I generate the registry, I need to understand auth in this project.**
>
> **Q1. Auth model** — pick the closest:
> - (A) **RBAC** — role-based: each user has a role that grants/restricts access (e.g., `admin`, `editor`, `viewer`)
> - (B) **API-key / token scopes** — callers present a key or JWT with scopes (e.g., `read:orders`, `write:orders`)
> - (C) **Ownership** — users can only access resources they own (e.g., `resource.userId === user.id`)
> - (D) **Open** — no auth on most endpoints (internal tool, trusted network, etc.)
> - (E) **Mixed or Other** — describe
>
> **Q2. What are the role/scope values?** (comma-separated — e.g., `admin, hr, viewer` or `read, write, admin`)
>
> **Q3. Where is auth enforced?** (e.g., API Gateway custom authorizer, per-handler RBAC check, Express middleware)
>
> **Q4. Is there a frontend auth layer?** If yes, describe briefly (e.g., route guards using a `UserRole` enum)

Store answers as `AUTH_MODEL`, `AUTH_ROLES`, `AUTH_ENFORCED_IN`, `FRONTEND_AUTH_NOTE`. Use them when generating every feature file's `**Model**:` line and `Access Condition` column.

---

## 6. Generate Feature Files

**Line budget**: each generated file must stay ≤ 400 lines. Be concise — tables over prose, 1-line descriptions, top 8 business rules max.

For each backend service, create `docs/features/{service-name}/index.md`:

```markdown
---
feature: {service-name}
type: backend-service
domain: {e.g., allocation-management, people-management}
criticality: high|medium|low
depends_on:
  - shared-backend
  - {other-service-if-any}
consumed_by:
  - {frontend-feature-name}
tags:
  - {domain-tag}
  - {capability-tag}
---

# {Service Name}

## Overview

| Field | Value |
|-------|-------|
| **Type** | Backend Service |
| **Package** | {package name} |
| **Path** | `{backend}/services/{service-name}/` |
| **Domain** | {domain} |
| **Last updated** | bootstrapped via /init-feature-registry |

## Domain Purpose
{1-2 sentences: what business problem this service solves and why it exists separately. NO file paths, handler names, or library names here — those belong in Key Files.}

## Entities Owned

| Entity | Description | Key Fields |
|--------|-------------|------------|
| `{table_name}` | {what it represents} | `id`, `status`, `created_at` |

## Status / State Machine

| Status | Business Meaning | Can Transition To | Trigger |
|--------|-----------------|-------------------|---------|
| `STATUS_A` | {meaning} | `STATUS_B`, `STATUS_C` | {what causes it} |

**Rules**: {transition constraints, one bullet per rule}

## Invariants
Non-negotiable system guarantees — AI must never violate these:
- {e.g., "Allocation percentage cannot exceed 100% per person per project"}
- {e.g., "Terminated persons cannot receive new allocations"}

## Access Control

**Model**: {RBAC | API-key | Ownership | N/A} — role/auth definitions in `.claude/rules/security.md`

| Endpoint / Action | Access Condition | Enforced In |
|-------------------|-----------------|-------------|
| {POST/PUT/DELETE action} | {role ∈ {admin} OR token.scope includes write OR user.id = resource.ownerId} | {handler / middleware} |
| {GET action} | {authenticated OR none} | {authorizer / guard} |

## Business Rules

Severity values: `CRITICAL` (data integrity/security invariant) | `HIGH` (business rule with real impact) | `MEDIUM` (operational concern) | `LOW` (quality concern)

| # | Rule | Enforced In | Severity |
|---|------|-------------|----------|
| BR-01 | {what the system prevents or requires} | `src/services/x.ts` | CRITICAL |

## External Integrations

| System | Trigger | What Happens |
|--------|---------|--------------|
| {Slack/GitHub/Linear/etc} | {event} | {result} |

## API Endpoints

| Method | Path | Auth | Who Uses It | Description |
|--------|------|------|-------------|-------------|
| `GET` | `/path` | required | `frontend-x` | {description} |

## Safe vs Dangerous Changes

### Safe
- {e.g., adding optional response fields}
- {e.g., adding new endpoints that don't change existing shapes}

### Dangerous — Requires Review
| Change | Risk | Why |
|--------|------|-----|
| {e.g., renaming enum values} | CRITICAL | {reason — who breaks and how} |
| {e.g., modifying constraint} | HIGH | {reason} |

### Human Escalation Required
- {e.g., schema migration that transforms existing data}
- {e.g., removing a Step Functions step}

## Known Error Scenarios

| Scenario | Error Returned | Root Cause |
|----------|---------------|------------|
| {scenario} | `400 CODE` | {why} |

## Testing Expectations

**Required test types**: {e.g., integration tests with real DB, unit tests for service methods}
**Critical assertions**:
- {e.g., "state transition tests cover all edges in the state machine"}
- {e.g., "authorization tests on every new endpoint"}

## Architectural Decisions

| Decision | Reason | Do Not Change Without |
|----------|--------|-----------------------|
| {e.g., EventBridge over direct HTTP call} | {reduce coupling} | {updating all consumers} |

## Forbidden Patterns
- Never {anti-pattern} — {reason}
- Never {anti-pattern} — {reason}

## Key Files
- `src/handlers/x.ts` — route definitions
- `src/services/x.ts` — business logic + rules
- `src/dto/x.ts` — request/response contracts
- `src/validations/x.ts` — input validation schemas

## Context Routing

### Optional
| Feature | Load when |
|---------|-----------|
| `{feature}` | {condition — e.g., "change touches lifecycle events"} |

### Workflow Loading Map
| Workflow | Sections to load |
|----------|-----------------|
| `/plan` | Full file — dependency graph in `docs/features/index.md` |
| `/implement-code` | Invariants + Business Rules + Key Files |
| `/pr-review` | Invariants + Business Rules + Change Risk Areas |
| `/requirements` | Domain Purpose + Invariants + Access Control + State Machine |
```

For each frontend feature, create `docs/features/{feature-name}/index.md`:

```markdown
---
feature: {feature-name}
type: frontend-feature
domain: {domain}
criticality: high|medium|low
depends_on:
  - {backend-service-primary}
consumed_by: []
tags:
  - {domain-tag}
---

# {Feature Name}

## Overview

| Field | Value |
|-------|-------|
| **Type** | Frontend Feature |
| **App** | {app name} |
| **Path** | `{frontend}/apps/app/{path}` |
| **Last updated** | bootstrapped via /init-feature-registry |

## What This Does for the User
{1-2 sentences: what business problem this solves. NO file paths, component names, or library names here.}

## Invariants
- {e.g., "Over-allocated persons (>100%) must always show a warning indicator"}
- {e.g., "Terminated persons must not appear in the allocation picker"}

## Access Control

**Model**: {RBAC | API-key | Ownership | N/A} — role/auth definitions in `.claude/rules/security.md`

| Page / Action | Access Condition | Enforced In |
|--------------|-----------------|-------------|
| {page or user action} | {role ∈ {admin} OR authenticated OR none} | {route guard / component guard} |

## Key User Flows

| Flow | Steps | Expected Outcome |
|------|-------|-----------------|
| {flow name} | 1. {step} 2. {step} | {outcome} |

## UI States

| State | When | What Shows |
|-------|------|------------|
| Loading | Data fetching | Skeleton / spinner |
| Empty | No records | Empty state + CTA |
| Error | API failure | Toast or inline error |
| Populated | Data loaded | {what renders} |
| {Domain state} | {condition} | {what shows} |

## APIs Consumed

| Method | Path | Service File | Used For |
|--------|------|-------------|---------|
| `GET` | `/path` | `services/x.ts` | {fetching what} |

## State (Redux)

| Slice | What It Holds | Key Selectors |
|-------|--------------|---------------|
| `xSlice` | {description} | `selectX`, `selectXLoading` |

## Safe vs Dangerous Changes

### Safe
- {e.g., adding new display fields}
- {e.g., adding new filter options}

### Dangerous — Requires Review
| Change | Risk | Why |
|--------|------|-----|
| {e.g., renaming Redux slice keys} | HIGH | {all selectors break} |

### Human Escalation Required
- {e.g., exposing data to new roles requires backend RBAC change}

## Testing Expectations

**Required test types**: {e.g., RTL component tests, Redux thunk tests}
**Critical assertions**:
- {e.g., "loading/error/empty states each have a dedicated test"}
- {e.g., "all interactive elements have data-testid attributes"}

## Architectural Decisions

| Decision | Reason | Do Not Change Without |
|----------|--------|-----------------------|
| {e.g., state in Redux not local} | {server data must survive navigation} | {updating all components reading this slice} |

## Forbidden Patterns
- Never {anti-pattern} — {reason}
- Never {anti-pattern} — {reason}

## Key Files
- `pages/X.tsx` — main page
- `services/x.service.ts` — API calls
- `libs/redux/slices/xSlice.ts` — state
- `libs/redux/thunks/xThunks.ts` — async actions

## Context Routing

### Optional
| Feature | Load when |
|---------|-----------|
| `{backend-service}` | {condition — e.g., "change adds a new API call"} |

### Workflow Loading Map
| Workflow | Sections to load |
|----------|-----------------|
| `/plan` | Full file — dependency graph in `docs/features/index.md` |
| `/implement-code` | Invariants + Key Files + APIs Consumed + State (Redux) |
| `/pr-review` | Invariants + UI States + Change Risk Areas |
| `/requirements` | What This Does + Invariants + Access Control + Key User Flows + UI States |
```

---

## 6b. Apply Auth Model to Feature Files

Use `AUTH_MODEL`, `AUTH_ROLES`, `AUTH_ENFORCED_IN`, and `FRONTEND_AUTH_NOTE` collected in Step 5b.

For every feature file generated:
- Set `**Model**:` in the Access Control section to the auth model type (e.g., `RBAC`, `API-key`, `Ownership`, `N/A`)
- Use actual role/scope values in the `Access Condition` column — never leave `{role}` placeholder text
- If auth is N/A for a feature (e.g., internal Lambda, EventBridge consumer), write `**Model**: N/A — invoked by trusted internal services only`

Do NOT write to `.claude/rules/security.md` here. If it was unpopulated, the user should run `/init-project-structure` — it infers the auth model from the actual code and persists it there — before re-running this skill's bootstrap.

---

## 7. Generate Master Index

Create `docs/features/index.md` — **must stay ≤ 250 lines**.

Populate the Mandatory Dependencies and Downstream Impact tables from what you discovered scanning the codebase in Steps 2–4 — direct imports, shared schema references, HTTP calls between services, frontend API consumers.

```markdown
---
registry_version: 2
last_updated: {date}
total_features: {N}
---

# Feature Registry

> **For agents**: Do not load all feature files. Use the Workflow Routing Rules to load only
> what the current ticket needs. Mandatory dependencies and downstream impact are in the
> Dependency Graph below — not in individual feature files.

---

## Workflow Routing Rules

**Step 1 — Match ticket keywords to feature domains:**

| If ticket mentions | Load these feature files first |
|-------------------|-------------------------------|
| {keyword, keyword} | `{feature}`, `{feature}` |

**Step 2 — Check the Dependency Graph below for mandatory dependencies and downstream impact**

**Step 3 — Load only the sections your workflow needs:**

| Workflow | Load |
|----------|------|
| `/plan` | Full feature file + Mandatory Dependencies table (this file) |
| `/requirements` | Domain Purpose + Invariants + Access Control + Flows + UI States |
| `/implement-code` | Invariants + Business Rules + Key Files + Mandatory Dependencies table (this file) |
| `/pr-review` | Invariants + Business Rules + Change Risk Areas + Downstream Impact table (this file) |

Project invariants and auth model are in `.claude/rules/` and auto-loaded — no explicit loading needed.

---

## Feature Catalog

### Backend Services
| Feature | Domain | Criticality | Path |
|---------|--------|-------------|------|
| `{service-name}` | {domain} | high | `backend/services/{name}/` |

### Frontend Features
| Feature | Domain | Criticality | Pages |
|---------|--------|-------------|-------|
| `{feature-name}` | {domain} | high | {page list} |

### Shared Rules (auto-loaded by Claude Code)
| File | Purpose |
|------|---------|
| `.claude/rules/security.md` | Auth model, enforcement pattern, role/scope definitions |
| `.claude/rules/backend-lang.md` | Language-level invariants, coding patterns |

---

## Dependency Graph

### High-Risk Couplings
| Coupling | Risk | Details |
|----------|------|---------|
| `{service-a}` → `{service-b}` | CRITICAL | {e.g., TypeScript direct import — circular risk} |
| `{webhook}` → `{service}` | MEDIUM | {e.g., HTTP POST — breaks if endpoint contract changes} |

### Shared Contracts
> Changing any of these requires updating ALL listed consumers simultaneously.

| Contract | Location | Consumers |
|----------|----------|-----------|
| `{entity}_status` enum | `{path}` | {service-a}, {frontend-x} |
| `{EventName}` payload | `{path}` | {emitter}, {consumer} |

### Mandatory Dependencies
> When loading a feature for `/plan` or `/implement-code`, also load these.

| Feature | Mandatory Dependencies |
|---------|----------------------|
| `{service}` | `{dep1}`, `{dep2}` |
| `{frontend}` | `{backend-service}`, `{frontend-libs}` |

### Downstream Impact
> Features that break when you change the feature in the left column. Load for `/pr-review`.

| Feature Changed | Downstream Impact |
|----------------|------------------|
| `{service}` | `{consumer-a}`, `{consumer-b}` |
| `{frontend-libs}` | all frontend features |
```

---

## 7b. Write Code-Wiki Content

`docs/features/` (just generated) is the terse, tabular AI-context registry. `code-wiki/{project-id}/`
is the human-readable rendering of the *same* underlying facts — architecture, per-feature
narrative pages, and the shared schema catalog — for a person reading the wiki, not an agent
loading context. This step writes that content from the same scan (Steps 2–4), reusing the
directory skeleton `/init-code-wiki` scaffolds and the format contract in its `SCHEMA.md`. It
never opens a new PR — code-wiki commits land on the same shared `wiki/init-scaffold` branch/PR
that `/init-code-wiki` and `/init-product-wiki` use. Where a written FEAT traces back to a
product-wiki decision, this step also calls `wiki-bridge-verifier` to check the link is real
before recording it — see "Bridge the FR ↔ FEAT Link" below.

### Guard — has code-wiki been scaffolded?

```bash
find code-wiki -maxdepth 2 -type d 2>/dev/null
```

If no `code-wiki/{project-id}/Architecture`, `Features`, and `Schemas` directories exist locally
or on the shared branch, tell the user to run `/init-code-wiki` first, then **skip the rest of
this step for this run** — `docs/features/` was already generated in Steps 1–7 and is unaffected
by code-wiki being unavailable.

### Determine `project-id` and target repository

Same derivation `/init-code-wiki` and `/init-product-wiki` use — from `CLAUDE.md`'s title — so
all three trees stay consistent without reading state back from one another:

```bash
GITHUB_REPO=$(grep '^GITHUB_REPO=' .claude/wiki-project.env 2>/dev/null | cut -d= -f2-)
[[ -z "$GITHUB_REPO" ]] && GITHUB_REPO=$(git remote get-url origin 2>/dev/null)
REPO_SLUG=$(echo "$GITHUB_REPO" | sed -E 's#^(https://github\.com/|git@github\.com:)##; s#\.git$##')
TARGET_REMOTE=$(git remote -v | awk -v url="$GITHUB_REPO" '$2 == url || $2 == url".git" {print $1; exit}')
[[ -z "$TARGET_REMOTE" ]] && TARGET_REMOTE="origin"
CURRENT_BRANCH=$(git branch --show-current)
```

### Write per-feature pages

For each feature, create or update `code-wiki/{project-id}/Features/{feature-name}/Index.md` —
using the exact same directory name that feature has under `docs/features/{feature-name}/`, so the
two trees stay in lockstep by name with no separate numbering scheme to maintain — per the
sections `code-wiki/{project-id}/SCHEMA.md` defines:

```markdown
# {Feature Name}

## Overview
{1-2 sentences, prose — same fact as the feature file's Domain Purpose / What This Does, in human phrasing rather than the AI-context table}

## Domain Purpose
{Domain Purpose / What This Does for the User, restated in prose}

## Key Flows
- {flow}: {steps, in prose — draw from Business Rules and Key User Flows already extracted for docs/features/}

## Business Rules
{prose restatement of the feature file's Business Rules table — narrative, not the severity table itself}

## Entities
- [{table_name}](../../Schemas/schemas.md#{table_name}) — {one-line description; link, don't restate columns}

## Recent Changes
- {date} — {ticket-id}: {one-line summary of what this ticket changed in this feature}
```

If `Index.md` already exists: **append** to Recent Changes rather than replacing it, and preserve
any content under a heading not listed in `SCHEMA.md` (e.g. a hand-written `## Notes` section) —
only the sections `SCHEMA.md` defines are scan-derived and safe to regenerate wholesale.

### Bridge the FR ↔ FEAT Link (Verify Against Product-Wiki)

This is the connector between code-wiki (reality: what's built) and product-wiki (intent: what
was asked for) — it doesn't belong inside either tree alone; a FEAT doesn't know what intent it
satisfies, and a feature-request doesn't know whether it's actually been built, without something
that names both sides. Skip this entire subsection if `wiki/{project-id}/` doesn't exist locally
or on the shared branch — product-wiki was never scaffolded via `/init-product-wiki`, so code-wiki
still gets written on its own above, with nothing to bridge against.

For each `{feature-name}/Index.md` just written, find the decision(s) that drove it:

1. Collect every ticket-id referenced in this Feat's `## Recent Changes` (including the one from
   this run).
2. For each ticket-id, grep `wiki/{project-id}/decisions/DEC-*.md` for a `linear_issue` field
   containing that ticket-id.
3. For each matching `DEC-NNNN`, read its `feature:` frontmatter field. If set (non-null), that's
   the linked feature-request: `wiki/{project-id}/feature-requests/{feature-id}/feature-request.md`.

If no decision matches any Recent Changes ticket-id, this FEAT was never tracked as a product
ask — most bug fixes and tech debt land here. Leave `{feature-name}/Index.md` without a
`## Relationships` section; that's expected, not a gap to fill.

If a match is found, call `wiki-bridge-verifier` (a stateless step, same convention as the
`wiki-*.md` steps `/wiki-ingest` follows — read its instructions and follow them inline, don't
invoke it as a separate command) with:
- The FR's current-state `## Requirements` and `## Business Rules` (from `feature-request.md`)
- This FEAT's `## Business Rules` and `## Key Flows` (the content just written above)

It returns a verdict — `verified` (every FR requirement/business rule has matching FEAT
behavior), `partial` (some do, some don't), or `unmatched` (none do) — plus a per-item breakdown.
Write both sides:

**`{feature-name}/Index.md`** — add (or update) a `## Relationships` section:
```markdown
## Relationships
**Implements:** [FR-{feature-id}](../../../../wiki/{project-id}/feature-requests/{feature-id}/feature-request.md) via [DEC-NNNN](../../../../wiki/{project-id}/decisions/DEC-NNNN_<slug>.md)
**Bridge Check:** {✅ Verified | ⚠️ Partial | ❌ Unmatched} — {one-line summary from wiki-bridge-verifier's output}
```

**`wiki/{project-id}/decisions/DEC-NNNN_<slug>.md`** — add one frontmatter field. This is the only
exception to that file's write-once discipline beyond `superseded_by` — same precedent, a single
targeted field, never a full rewrite:
```yaml
implemented_by: {feature-name}
```

Never silently upgrade a `partial`/`unmatched` verdict to `verified`, and never skip writing the
`## Relationships` section because the verdict wasn't clean — an unmet requirement next to the
code that was supposed to satisfy it is exactly the signal a human needs to see. This check is
advisory: report a `partial`/`unmatched` verdict (Step 9) and still write it into both files, but
never block the rest of this run or the code-wiki commit on it.

### Write `Architecture/Overview.md`

Create or update `code-wiki/{project-id}/Architecture/Overview.md` — system-wide shape only, never
a single feature's internals:
- Service/app topology and how they talk to each other (from the Dependency Graph built in Step 4)
- Tech stack / architecture style per layer (from the architecture detection in Step 2)
- Cross-cutting architectural decisions that recur across 2+ features (a decision scoped to one
  feature belongs in that feature's own `Index.md` `Architectural Decisions` table instead, not
  duplicated here)
- The coupling graph implied by `docs/features/index.md`'s High-Risk Couplings and Mandatory
  Dependencies tables (a text or mermaid rendering)

Preserve any manually-added sections not covered above, same rule as per-feature pages.

### Write `Schemas/schemas.md`

Create or update `code-wiki/{project-id}/Schemas/schemas.md` from the DB migrations read in Step
2e — one row per entity, full column/constraint detail, written once here rather than restated
per-feature:

```markdown
# Schemas — {Project Name}

| Entity | Owning Feature | Columns | Constraints | Cross-Feature FKs |
|--------|----------------|---------|--------------|-------------------|
| `{table}` | [{feature-name}](../Features/{feature-name}/Index.md) | {name:type, ...} | {unique/check/FK} | {table.col → other_table.col (owned by {other-feature-name})} |
```

Only mark an FK "cross-feature" when the two tables are owned by different features — same-feature
FKs stay implicit in the entity's own row.

### Commit onto the shared branch

Code-wiki commits land on `wiki/init-scaffold`, never the current ticket branch — stash the
generated `code-wiki/` changes (plus any `wiki/{project-id}/decisions/DEC-*.md` edited by the
bridge step above — same branch, same commit), switch over, commit, push, then switch back so
the ticket branch is left untouched:

```bash
git stash push -u -m "code-wiki-pending" -- code-wiki/ wiki/
git fetch "$TARGET_REMOTE" wiki/init-scaffold
git checkout wiki/init-scaffold 2>/dev/null || git checkout -b wiki/init-scaffold "$TARGET_REMOTE"/main
git stash pop
git add code-wiki/ wiki/
git commit -m "docs: update code-wiki from /init-feature-registry rescan ({TICKET_ID})"
git push "$TARGET_REMOTE" wiki/init-scaffold
git checkout "$CURRENT_BRANCH"
```

If `git stash pop` conflicts (the shared branch has code-wiki content this checkout doesn't have
locally), resolve in favor of keeping both — this branch is additive across many rescans, not a
single owner's working copy.

Then check whether a PR is already open — never open a second one:

```bash
gh pr list --repo "$REPO_SLUG" --head wiki/init-scaffold --state open --json url,number
```

If none is open, tell the user — code-wiki content was pushed to the branch but nothing is open
to review it in yet; point them at `/init-code-wiki` or `/init-product-wiki`, either of which
opens the shared PR.

---

## 8. Commit

```bash
git add docs/features/
git commit -m "docs: bootstrap feature registry via /init-feature-registry"
```

This commits `docs/features/` on the **current ticket branch** — separate from the code-wiki
commit in Step 7b, which lands on the shared `wiki/init-scaffold` branch instead.

---

## 9. Report

Tell the user:
- How many feature files were generated
- How many consumer relationships were discovered
- Which areas had sparse documentation (few business rules found — worth manually enriching)
- Whether code-wiki was updated (and its PR URL) or skipped because `/init-code-wiki` hasn't run yet
- Every FR ↔ FEAT bridge check that ran and its verdict — call out any `partial`/`unmatched` by
  name (feature-id and the specific unmet item), not just a count
- Remind them: run `/update-feature-registry` at the end of each ticket to keep it current, and `/plan` will now automatically read it for impact analysis

---

## Rules

- Generate a file for every service/feature found — do not skip
- If a field value cannot be determined from code, write `(unknown — needs manual fill-in)` rather than omitting it
- Business rules are the most valuable part — spend extra time reading service files fully (Step 2c), not just method signatures
- Do not invent business rules — only document what is explicitly enforced in code
- DB migration constraints (Step 2e) are authoritative business rules — a GiST exclusion or unique index IS a business rule even if the service code doesn't mention it
- Cross-service TypeScript imports (Steps 2f, 4b) are the highest-risk couplings — never omit them from the Dependency Graph
- Redux slice state shapes (Step 3a) must be read from slice files, not guessed from feature names
- Security guard functions (Step 2h) must be documented as CRITICAL business rules — never omit them
- Companion packages (Step 2 companion detection) that share a domain belong in a single feature file — do not generate separate files for HTTP API layer + Lambda handler layer of the same feature
- Multi-domain services (e.g., allocation + timesheet in one service) must document BOTH domains — separate state machines, separate entity tables, all handler files
- Keep API shapes at field name + type level — no implementation code in the registry
- Sparse is better than wrong — a partial entry with `(unknown)` markers is more useful than a confident but incorrect one
- `Domain Purpose` and `What This Does for the User` must contain zero file paths, handler names, or library names — business language only
- Use only `CRITICAL`, `HIGH`, `MEDIUM`, `LOW` in all severity columns — never "Hard block", "Soft block", or custom values
- After generating all files, verify: every feature has an Access Control section with real role/scope values (no placeholders), every CRITICAL business rule has a corresponding Forbidden Patterns entry, every cross-service import from Step 4b appears in the Dependency Graph, and the Mandatory Dependencies + Downstream Impact tables in `docs/features/index.md` are fully populated
- Code-wiki (Step 7b) is additional, derived content — never a substitute for `docs/features/`. If `/init-code-wiki` hasn't been run yet, skip Step 7b entirely rather than scaffolding code-wiki directories yourself; that scaffold is that skill's job
- `code-wiki/{project-id}/Features/{feature-name}/` uses the exact same directory name as `docs/features/{feature-name}/` — no separate numbering scheme, so there is nothing to assign or renumber; if a service/feature is renamed, rename both directories together
- Code-wiki commits always land on the shared `wiki/init-scaffold` branch (Step 7b), never the current ticket branch, and never open a second PR if one is already open on that branch
- Preserve manually-edited content in code-wiki files (anything under a heading `SCHEMA.md` doesn't define, and prior `Recent Changes` entries) — only regenerate the sections `SCHEMA.md` defines as scan-derived
- Only write a `## Relationships` section, or a decision's `implemented_by` field, from an actual `DEC-NNNN` matched via a Recent Changes ticket-id (see "Bridge the FR ↔ FEAT Link") — never guess a link from name similarity alone
- Skip the bridge check entirely (no error, no partial attempt) when `wiki/{project-id}/` doesn't exist — code-wiki has no product-wiki to link against yet, and that's a normal, expected state
- The bridge check is advisory, never a gate — a `partial`/`unmatched` `wiki-bridge-verifier` verdict still gets written into both `{feature-name}/Index.md` and the decision's `implemented_by` field, and is called out in Step 9's report; it never blocks the code-wiki commit or the rest of this run
