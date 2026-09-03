---
name: init-code-wiki
description: One-time onboarding initialization of a project's code-wiki — scaffolds code-wiki/{project-id}/, then deep-scans the codebase via parallel exploration subagents and writes the populated tree (Architecture/Overview.md, Features/Feat-NNNN-*/Index.md, Features/index.md, Schemas/schemas.md), pushed as a PR to the project's repository. The code wiki is the source of truth about the codebase; this skill is what makes it true. Supersedes /init-feature-registry, whose scan work it absorbs. Shares one branch/PR with /init-product-wiki.
disable-model-invocation: true
allowed-tools:
  - Read
  - Write
  - Glob
  - Bash
  - Agent
---

# Init Code Wiki

Initialize a project's **code-wiki** — the codebase-derived documentation tree (architecture,
features, schemas), as opposed to the product-derived `wiki/` created by `/init-product-wiki`
(decisions and feature *requests*).

**The code wiki is the single source of truth about what this codebase actually is.** There is no
second store: this skill absorbs the full codebase scan that `/init-feature-registry` used to
perform into `docs/features/`, and writes the result into the code wiki's own shape. That skill is
superseded and should not be run — see its own banner.

So this skill does two things in one run: it scaffolds the tree, then it **fills it** —
`Architecture/Overview.md`, one `Features/Feat-NNNN-{feature-id}/Index.md` per feature, a generated
`Features/index.md`, and `Schemas/schemas.md`. A scaffolded-but-empty code wiki is not a useful
outcome: every consumer that reads it (`/plan`'s impact analysis, the alignment loop's check on
whether a ticket's claims match reality) treats "no feature found" as "no such feature exists",
so an empty tree does not read as *unknown*, it reads as *nothing is built*.

The scan is done by **parallel exploration subagents**, not by this session reading the whole repo
itself. That is what makes a deep scan affordable — see Step 5a.

**This is a one-time onboarding step.** It runs once per project, ever — see the Guard below and
`docs/ONBOARDING.md`, which points to this skill as part of first-time setup.

## The Target Shape

This is what a completed run produces:

```
code-wiki/
└── {project-id}/
    ├── SCHEMA.md
    ├── Architecture/
    │   └── Overview.md
    ├── Features/
    │   └── Feat-0001-{feature-id}/
    │       └── Index.md
    └── Schemas/
        └── schemas.md
```

In production this is **one repo, one project, one code-wiki** — `code-wiki/{project-id}/` is one
full instance of everything below.

**`SCHEMA.md`** — the one place that pins down file/section format so an LLM writing or updating
`Features/*/Index.md` doesn't drift from file to file. Not to be confused with `Schemas/schemas.md`
below — this one is about *documentation* format, not database schema.

**`Architecture/Overview.md`** — system-wide shape, not any single feature's internals: the
service/app topology and how they talk to each other (this is where a diagram of the coupling
graph implied by `Features/` dependencies would live visually), the tech stack / architecture
style per layer, and cross-cutting architectural decisions that aren't scoped to one feature
(e.g. "EventBridge over direct HTTP calls" — a whole-codebase choice, not something that belongs
duplicated into every feature file's own decisions table).

**`Features/`** — one `Feat-NNNN-{feature-id}/` folder per feature this run documents, plus a
generated `index.md` carrying the catalog, the workflow routing rules and the dependency graph.

**`Schemas/schemas.md`** — the canonical, whole-codebase database schema: full column lists (name,
type, constraints — unique/check/FK) written once here rather than restated per feature; an
ownership column naming which `Feat-*` has primary read/write authority over each table; and
relationships/FKs that cross feature boundaries (e.g. `orders.user_id → users.id` where `orders`
and `users` are owned by different features) — inherently shared, so it can't live inside a single
feature file.

---

## Directory Structure This Skill Creates

```
code-wiki/
└── {project-id}/
    ├── SCHEMA.md
    ├── Architecture/
    │   └── .gitkeep
    ├── Features/
    │   └── .gitkeep
    └── Schemas/
        └── .gitkeep
```

Git does not track empty directories, so each gets a bare `.gitkeep` at scaffold time — a
placeholder purely so the folder survives the first commit. Leave them in place once the directory
gains real files; they are harmless.

Steps 5a–5c then populate `Architecture/Overview.md`, `Features/Feat-NNNN-*/Index.md`,
`Features/index.md`, and `Schemas/schemas.md` in the same run, as further commits on the same
branch.

## 1. Guard — Initialize, or Refresh?

**Two modes, and the caller states which.** Read this before the guard below, because the guard
means different things in each.

| Mode | Invoked by | What it does |
|---|---|---|
| **initialize** (default) | onboarding, or a human running `/init-code-wiki` | Scaffold the tree, then scan and populate it. Stops if the tree already exists. |
| **refresh** | `/implement`'s `UPDATE_FEATURE_REGISTRY` phase, at the end of a ticket, or a human asking to refresh | Skip scaffolding entirely; re-run the scan (5a–5c) and rewrite content over the existing tree. |

Per-ticket closeout (`closeout-feat-recorder`) is **not** a caller of either mode above — it writes `code-wiki/**` directly from the delivered diff on the PR's own branch, and never invokes this skill.

Treat the run as **refresh** when the caller says refresh/update/rescan, or when the tree already
exists and the caller clearly wants it brought current rather than created. When it is genuinely
ambiguous, prefer refresh over stopping if the tree exists — a stale code wiki that consumers
treat as fact is worse than one rewritten a second time.

**Refresh must never:**
- re-create structure or drop a `.gitkeep`
- renumber an existing `Feat-NNNN` — resolve each target to its existing directory by
  `feature` slug first, and only assign a new number to a target with no existing directory
- overwrite `SCHEMA.md`
- delete a feature directory whose target no longer appears in the scan. A feature that has
  genuinely been removed from the codebase is a real event, and silently deleting its page
  destroys the record; leave the page and add `*Open question: no source found for this feature
  in the latest scan — was it removed, renamed, or did the scan miss it?*` to it. A scan gap and
  a deletion look identical from here, and only one of them is safe to act on.

The rest of this step is the **initialize**-mode guard. In refresh mode, skip to Step 5a.

This scaffold may live on the shared `wiki/init-scaffold` branch and not yet be merged to `main`,
so check both places before concluding it hasn't run.

Check the current branch's working tree first:

```bash
find code-wiki/{project-id} -maxdepth 1 -type d 2>/dev/null
```

If that finds `Architecture`, `Features`, and `Schemas` already, **stop** — tell the user the
code-wiki is already initialized, and that bringing it current is a **refresh** run rather than
another initialize (see the mode table above). Do not silently refresh on their behalf here: an
initialize request against an existing tree usually means the caller did not know it existed, and
they should decide.

If nothing turns up locally, also check whether the shared scaffold branch has it already on the
target repository, in case it exists there but hasn't been merged or checked out here. Resolve the
target remote the same way Step 3 does — this workspace's own `origin`:

```bash
GITHUB_REPO=$(git remote get-url origin 2>/dev/null)
TARGET_REMOTE="origin"
git fetch "$TARGET_REMOTE" wiki/init-scaffold 2>/dev/null && git ls-tree -r "$TARGET_REMOTE"/wiki/init-scaffold --name-only | grep "^code-wiki/{project-id}/"
```

If that returns anything, stop for the same reason — point the user at the open PR on that branch
(Step 8 shows how to find it) rather than re-scaffolding. If there's no `origin` remote configured
yet, this simply finds nothing to fetch — harmless, the local-directory check above is what
actually matters in that case.

## 2. Determine `project-id`

In production this is **one repo, one project, one code-wiki** — the `project-id` is this
project. Derive it (kebab-case, e.g. `billing-export-service`) from `CLAUDE.md`'s title, or ask
the user if ambiguous. This is the same deterministic derivation `/init-product-wiki` uses, so it
stays consistent with `wiki/{project-id}/` without needing to read anything back from a shared
file — the two trees describe the same project and should not drift to different ids.

## 3. Determine the Target Repository

The target repository is this workspace's own `origin` remote:

```bash
git rev-parse --show-toplevel 2>/dev/null
GITHUB_REPO=$(git remote get-url origin 2>/dev/null)
```

If this isn't a git repo yet, or has no `origin` remote configured, **ask the user** for the
project's repository URL (e.g. `git@github.com:org/repo.git`) — don't guess or invent one — then:
```bash
git init 2>/dev/null   # only if not already a repo
git remote add origin {url}
GITHUB_REPO={url}
```

Resolve `$REPO_SLUG` — the `owner/repo` form `gh --repo` needs — from `$GITHUB_REPO`, and set
`$TARGET_REMOTE` to `origin`, the only remote this skill ever fetches/pushes through:
```bash
REPO_SLUG=$(echo "$GITHUB_REPO" | sed -E 's#^(https://github\.com/|git@github\.com:)##; s#\.git$##')
TARGET_REMOTE="origin"
```

## 4. Determine the Shared Wiki Branch

`/init-code-wiki` and `/init-product-wiki` share **one** fixed branch name, `wiki/init-scaffold`,
and one PR on it — so this skill's own content commits, and any later content-writer
(`/seed-wiki-content`, `/wiki-ingest`), always have a single unambiguous place to commit into. Both skills simply target this constant name
directly; there's no shared state to read or originate first.

## 5. Create the Directories and `SCHEMA.md`

```bash
mkdir -p code-wiki/{project-id}/Architecture
mkdir -p code-wiki/{project-id}/Features
mkdir -p code-wiki/{project-id}/Schemas
touch code-wiki/{project-id}/Architecture/.gitkeep
touch code-wiki/{project-id}/Features/.gitkeep
touch code-wiki/{project-id}/Schemas/.gitkeep
```

Then write `code-wiki/{project-id}/SCHEMA.md` — **only if it doesn't already exist**; never
overwrite one, since a project may have tightened it since onboarding.

````markdown
# Code Wiki Schema

Documentation-format contract for this project's `code-wiki/`. **This tree is the source of
truth about the codebase** — business rules, invariants and entity definitions live here and
are not a rendering of anything else. Write for the agent about to change this code, not for
a reader browsing documentation.

## Frontmatter (every Features/*/Index.md)

```yaml
feat_id: Feat-NNNN          # canonical, assigned once, never renumbered
feature: {slug}             # kebab-case name; may change without changing feat_id
type: backend-service | frontend-feature | shared-library
domain: {business-domain}
criticality: high | medium | low
touched_paths:              # the source paths this feature owns
  - {path}
depends_on: [{feat_id or slug}, ...]      # edges are canonical HERE
consumed_by: [{feat_id or slug}, ...]
implements: [FR-*, ...]     # bridge to product intent in wiki/; [] if none known
tags: [{domain-tag}, {capability-tag}]
```

`depends_on`/`consumed_by` are the **only** authoritative record of the dependency graph.
`Features/index.md` and the coupling graph in `Architecture/Overview.md` are generated views
of these fields — never hand-maintain an edge in either, and never let one disagree.

## Features/Feat-NNNN-{feature-id}/Index.md

`Feat-NNNN` is assigned once per feature by scanning existing `Feat-NNNN-*` directories for
the current max and incrementing. **Never renumber an existing directory** — a rename changes
`feature`, never `feat_id`.

**Line budget: 400 lines.** When tight, omit in this order:
- **Optional, omit first** — Status/State Machine, External Integrations, Architectural Decisions
- **Recommended, omit only if forced** — Entities Owned, User Roles, Forbidden Patterns, Testing Expectations, Known Error Scenarios
- **Required, never omit** — Domain Purpose, Invariants, Business Rules, Safe vs Dangerous Changes, Key Files, Context Routing

Prefer tables over prose, one-line descriptions, and at most the top 8 business rules.

Sections, for `type: backend-service` and `shared-library`:

| Section | Form |
|---|---|
| Overview | table: Type, Package, Path, Domain, Last updated |
| Domain Purpose | 1–2 sentences on the business problem. No file paths or library names — those are Key Files |
| Entities Owned | table: Entity → link to `../../Schemas/schemas.md#{table}` → what it represents. **Never restate columns** — `Schemas/schemas.md` holds them once |
| Status / State Machine | table: Status, Business Meaning, Can Transition To, Trigger; plus transition constraint bullets |
| Invariants | bullets. Non-negotiable guarantees an agent must never violate |
| Access Control | `**Model**:` line, then table: Action, Access Condition, Enforced In |
| Business Rules | table: `BR-NN`, Rule, Enforced In (`file:line`), Severity. Severity is `CRITICAL` (data-integrity/security invariant), `HIGH` (real business impact), `MEDIUM` (operational), `LOW` (quality) |
| External Integrations | table: System, Trigger, What Happens — includes async processes (scheduled jobs, queue consumers, webhooks) |
| API Endpoints | table: Method, Path, Auth, Who Uses It, Description |
| Safe vs Dangerous Changes | `### Safe` bullets; `### Dangerous — Requires Review` table (Change, Risk, Why — who breaks and how); `### Human Escalation Required` bullets |
| Known Error Scenarios | table: Scenario, Error Returned, Root Cause |
| Testing Expectations | required test types, plus critical-assertion bullets |
| Architectural Decisions | table: Decision, Reason, Do Not Change Without. Only this feature's own — recurring ones belong in `Architecture/Overview.md` |
| Forbidden Patterns | bullets: `Never {pattern} — {reason}` |
| Key Files | bullets: `path — role` |
| Context Routing | optional-load table (Feature, Load when) and a per-workflow section-loading table |

For `type: frontend-feature`, replace API Endpoints / Entities Owned / Status with:

| Section | Form |
|---|---|
| What This Does for the User | 1–2 sentences, user-facing |
| Key User Flows | per flow: the user action and what happens |
| UI States | table: Condition, What Renders — including domain-meaning states (a limit exceeded, an archived record) |
| APIs Consumed | table: Method, Path, Owning `Feat-NNNN` |
| State | the store slice, its shape, and its exported selectors |

A section with nothing found writes `*None found.*` — never a plausible guess. A section
whose answer could not be determined writes `*Open question: {the question}.*` See the
"unknowns" rule below.

## Features/index.md — GENERATED

Regenerated from frontmatter; never hand-edited. Holds:
- **Feature Catalog** — one table per `type`: `feat_id`, feature, domain, criticality, path
- **Workflow Routing Rules** — the keyword → feature-file table, and the per-workflow
  section-loading table. This is how a consumer avoids loading the whole tree
- **Dependency Graph** — mandatory dependencies and downstream impact, derived from
  `depends_on`/`consumed_by`

## Architecture/Overview.md

System topology, tech stack per layer, cross-cutting architectural decisions (only those
recurring across 2+ features — a single feature's own decision lives in that feature's file),
and the coupling graph rendered from frontmatter edges.

## Schemas/schemas.md

One entry per entity: full column list (name, type, nullability, default), constraints
(unique/check/exclusion/FK) with the migration that introduced each, the owning `Feat-NNNN`,
and foreign keys that cross feature boundaries. **Written once here, never duplicated
per-feature** — a feature links to an anchor in this file instead.

Where a migration and an application-level schema definition disagree, **the migration is the
truth** and the disagreement is recorded as a finding.

## Unknowns

Never fabricate. A fact the scan could not establish is written as
`*Open question: {the question}.*` in the section where it belongs. An explicit open question
is a useful artifact; an invented answer is indistinguishable from a real one and silently
poisons every consumer downstream.
````

## 5a. Explore the Codebase — via Subagents

**Do not scan the repo yourself.** Dispatch the `Agent` tool, in parallel, and compose what
comes back. This is not a stylistic preference: a full scan is nine backend passes and four
frontend passes per target plus repo-wide edge discovery, and reading all of that into this
session's own context would exhaust the run's turn budget long before any file got written.
Each subagent burns its own context on file reading and returns only findings.

**Exploration is cheap and parallel; synthesis is not.** The scanners run on a small fast
model. Composing their findings into the wiki — Step 5c — stays on this session's model,
because that is where judgment about what matters actually happens.

**First, enumerate targets** (cheap, do it here):

```bash
# Backend service / module roots
find . -maxdepth 3 -type d \( -name "services" -o -name "modules" -o -name "packages" -o -name "apps" \) \
  -not -path "*/node_modules/*" -not -path "*/dist/*" 2>/dev/null
# Frontend feature areas
find . -maxdepth 4 -type d \( -name "pages" -o -name "features" -o -name "views" -o -name "routes" \) \
  -not -path "*/node_modules/*" -not -path "*/dist/*" 2>/dev/null
```

**Then dispatch, all in one message so they run concurrently:**

- **one `codebase-scanner` per target** — `subagent_type: codebase-scanner`. Tell each
  exactly which service or feature area is its target and nothing else. Two directories
  sharing a domain (same nouns, cross-imports) are one target; the agent will confirm or
  correct that.
- **one `schema-scanner`** — `subagent_type: schema-scanner`. Repo-wide entity catalog.
- **one `dependency-mapper`** — `subagent_type: dependency-mapper`. Dispatch this **after**
  the scanners return, and pass it the target list plus the endpoints they reported: it maps
  edges *between* targets, which no single-target scanner can see.

If a scanner returns nothing usable for a target, say so in the report and write that
feature's file from what the other passes did establish, with explicit open questions for the
rest. **Never re-run a scanner hoping for a better answer without changing the prompt**, and
never fill its gap from your own expectations of what a project like this contains.

**Model fallback.** The three agents pin a small fast model in their own frontmatter. If this
workspace cannot use it, the dispatch fails rather than silently costing 20× — remove the
`model:` line from the agent file to inherit the session's model, and say in the report that
exploration ran on the inherited model so the cost is attributable.

## 5b. Derive the Auth Model — Never Ask

`/init-feature-registry` stopped here and asked the user four questions (auth model, role
values, enforcement point, frontend layer) before it would write any Access Control section.
**This skill never asks.** It runs headless under onboarding, where there is no one to answer
and a blocking question is a hung run.

Derive instead, from what the scanners already returned:
- the security-guard pass — the functions that are the sole enforcement point for an access
  rule, and what each protects
- the role/scope enum or constant, wherever it is defined
- role-based conditional rendering on the frontend
- middleware, authorizer and framework security configuration

From that, state the model (role-based, token/scope-based, ownership-based, open, or mixed),
the actual role or scope values found, and where enforcement lives — **each cited to a
`file:line` a reader can check.**

Whatever you cannot establish this way becomes an explicit open question in the feature file
that needed it — `*Open question: is /admin/* enforced anywhere besides the frontend route
guard?*`. Do not infer an auth model from framework conventions, and do not describe a project
as "role-based" because it has a `role` column. A wrong access-control description is worse
than a missing one: an agent reading it will trust it while changing exactly the code that
enforces access.

## 5c. Write the Code Wiki

Compose the findings into the tree, following `SCHEMA.md` exactly — it is the contract, and
this step is its first consumer.

1. **Assign `Feat-NNNN`.** Scan existing `Feat-NNNN-*` directories for the current max and
   increment from there. Stable order, so a re-run on an unchanged repo produces the same
   numbers: sort targets by kind (backend-service, then frontend-feature, then shared-library)
   then by name. Never renumber an existing directory.
2. **`Schemas/schemas.md` first** — the feature files link into its anchors, so it must exist
   before they can be checked.
3. **One `Features/Feat-NNNN-{feature-id}/Index.md` per target**, with the frontmatter and the
   tiered section set. Fill `depends_on`/`consumed_by` from the dependency-mapper's edges and
   `touched_paths` from what the scanner actually found. `implements` stays `[]` unless the
   product wiki already carries a matching `FR-*`; guessing the bridge is worse than leaving
   it empty for `/seed-wiki-content` and the alignment loop to establish later.

   Where you do set `implements`, run `/wiki-bridge-verifier` on that pair and write its
   verdict into the page. It is **advisory, not a gate** — write the link and the verdict
   even when the verdict is `partial` or `unmatched`. Withholding the link hides exactly the
   intent-versus-reality mismatch a human needs to see.
4. **`Architecture/Overview.md`** — topology, stack per layer, the cross-cutting decisions that
   recur across two or more features, and the coupling graph rendered from the frontmatter
   edges.
5. **`Features/index.md` last**, generated from the frontmatter you just wrote: catalog,
   workflow routing rules, dependency graph. It is a view — if generating it surfaces an edge
   that disagrees with a feature's frontmatter, fix the frontmatter, never the view.

Respect the 400-line budget per feature file and the omission order in `SCHEMA.md`. A file
over budget is not a thorough file, it is one that will not be loaded.

## 6. Confirm Before Pushing

Before touching git history or opening/updating a PR, show the user:
- the target repo (from Step 3) and branch name (`wiki/init-scaffold`, from Step 4)
- exactly what's about to be committed — the whole `code-wiki/{project-id}/` tree, split into
  "new" and "updated", with the feature count and the number of open questions written into it.
  The open-question count is the honest measure of how much the scan could not establish, and the
  user should see it before this becomes the project's source of truth
- whether a PR will be **created** (no open PR found for this branch — see Step 8) or an existing
  one will simply gain a new **commit** (a PR for this branch already exists)

Get explicit go-ahead before proceeding — pushing and opening a PR are visible, shared-state
actions.

## 7. Branch, Commit, Push

```bash
git fetch "$TARGET_REMOTE"
git checkout wiki/init-scaffold 2>/dev/null || git checkout -b wiki/init-scaffold "$TARGET_REMOTE"/main 2>/dev/null || git checkout -b wiki/init-scaffold
git add code-wiki/{project-id}
git commit -m "chore: scaffold code-wiki directory structure for {project-id}"
git push -u "$TARGET_REMOTE" wiki/init-scaffold
```

## 8. Create or Reuse the PR

Check GitHub directly for an existing open PR on this branch — this is the authoritative check,
there's no local state file to consult:

```bash
gh pr list --repo "$REPO_SLUG" --head wiki/init-scaffold --state open --json url,number
```

- **If a PR is returned** — one already exists (opened by `/init-product-wiki` or a prior run).
  Nothing further to do; the commit just pushed lands on it automatically.
- **If none is returned** — this skill is the first of the two to reach this point. Create it:
  ```bash
  gh pr create --repo "$REPO_SLUG" --draft --title "Scaffold project wiki (code-wiki + product wiki)" --body "$(cat <<'EOF'
  ## Summary
  - Scaffolds code-wiki/{project-id}/ (Architecture/, Features/, Schemas/ — empty, .gitkeep only)
  - Long-lived scaffold PR: a Temporal Agent commits actual wiki content here as it's written
  - Do not merge until the wiki has real content — this PR is the living wiki changeset

  🤖 Generated with [Claude Code](https://claude.com/claude-code)
  EOF
  )"
  ```

## 9. Report

Tell the user:
- The PR URL (whether newly created or already existing)
- `SCHEMA.md` was created, or already existed and was left untouched
- **How many features were documented**, by type, with their `Feat-NNNN` ids
- **How many entities** are in `Schemas/schemas.md`, and how many foreign keys cross feature
  boundaries
- **Every open question written into the tree**, listed — not just counted. These are the things
  the scan could not establish, and they are the follow-up work this run generated. A run that
  reports zero open questions on a codebase of any size has probably invented something
- Which targets, if any, returned nothing usable from their scanner, and what was written for them
  anyway
- Whether exploration ran on the pinned small model or fell back to the inherited one — this is
  the difference between a cheap run and an expensive one, and it should not be silent
- Which mode ran — **initialize** or **refresh**. On a refresh, also report which feature pages
  were rewritten, which were newly added, and which have no source found any more (each of those
  now carries an open question rather than having been deleted)

---

## Rules

- **The code wiki is the source of truth about the codebase.** There is no second store and no
  parallel registry. Do not write `docs/features/`, and do not treat this tree as a rendering of
  anything else.
- **Never fabricate a finding.** Anything the scan could not establish is written as an explicit
  `*Open question: ...*` in the section that needed it. An invented answer cannot be told apart
  from a real one by any later reader, which makes it strictly worse than a gap.
- **Never ask the user a question in order to proceed.** This runs headless under onboarding.
  Derive what you can (Step 5b) and record the rest as open questions.
- **Dispatch subagents for the scan; never read the whole repo in this session** (Step 5a). The
  turn budget will not survive it, and a run that dies mid-scan leaves a half-written tree.
- Skip writing `SCHEMA.md` if it already exists — never overwrite it; a project may have
  tightened its own contract since onboarding.
- `Features/index.md` and the coupling graph are **generated views** of frontmatter. When one
  disagrees with a feature file, the frontmatter wins and the view is regenerated.
- `Feat-NNNN` is assigned once and never renumbered. A rename changes `feature`, not `feat_id`.
- **Scaffolding is one-time; scanning is not.** Never re-scaffold if `code-wiki/{project-id}/`
  already exists in the working tree or on the shared branch (Step 1). A refresh run rescans and
  rewrites content over that existing structure and touches neither the directories nor
  `SCHEMA.md`.
- **A refresh never deletes a feature page** and never renumbers one. A missing source is
  indistinguishable here from a scan that missed it, so it becomes an open question on the page,
  not a deletion.
- Share the branch and PR with `/init-product-wiki` — always check `gh pr list --repo
  "$REPO_SLUG" --head wiki/init-scaffold` before creating one; never open a second PR if one is
  already open.
- **The target repository is always this workspace's own `origin` remote** (Step 3) — resolve
  `$REPO_SLUG` from it and use `origin`, plus `gh --repo`, for every git/gh operation.
- Never invent a git remote URL — if `origin` isn't configured, ask the user for it.
- Always confirm with the user (Step 6) before pushing or creating a PR.
- Keep `project-id` consistent with `wiki/{project-id}/` if a product-wiki already exists for this
  project — one repo, one project, one id, across both trees, derived the same way (from
  `CLAUDE.md`'s title) so there's nothing to drift.
