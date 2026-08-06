---
name: init-product-wiki
description: One-time onboarding scaffold of the product-wiki directory structure — wiki/SCHEMA.md and wiki/{project-id}/ with index.md, feature-requests/index.md, and decisions/index.md — pushed as a PR to the project's repository. Creates structure only, no decision or feature-request content. Shares one branch/PR with /init-code-wiki so /wiki-ingest can later commit wiki content into the same PR.
disable-model-invocation: true
allowed-tools:
  - Read
  - Write
  - Glob
  - Bash
---

# Init Product Wiki

Scaffold the empty directory structure for a project's product wiki. **This skill only creates
structure** — `wiki/SCHEMA.md` (the one static schema-definition file, written once) plus empty
index files with header rows and no data. It never writes a `DEC-NNNN_<slug>.md` decision record
or a `feature-requests/{feature-id}/feature-request.md` file — those are written later, by
`/wiki-ingest` (the "temporal agent" — see `.claude/skills/wiki-ingest/SKILL.md`), the first time
an actual meeting produces a decision or feature-request to record.

**This is a one-time onboarding step.** It runs once per project, ever — see the Guard below and
`docs/ONBOARDING.md`, which points to this skill as part of first-time setup.

## Directory Structure This Skill Creates

```
wiki/
├── SCHEMA.md
└── {project-id}/
    ├── index.md
    ├── feature-requests/
    │   └── index.md
    └── decisions/
        └── index.md
```

Nothing else. 

## 1. Guard — Has This Already Run?

This scaffold may live on the shared `wiki/init-scaffold` branch and not yet be merged to `main`,
so check both places before concluding it hasn't run.

Check the current branch's working tree first:

```bash
find wiki/{project-id} -maxdepth 2 -name "*.md" 2>/dev/null
```

If `index.md`, `feature-requests/index.md`, or `decisions/index.md` already exist for this
`project-id`, **stop** — tell the user the product wiki was already scaffolded and this skill is a
one-time onboarding step, not a recurring one.

If nothing turns up locally, also check whether the shared scaffold branch has it already on the
target repository, in case it exists there but hasn't been merged or checked out here. Resolve the
target remote the same way Step 3 does — this workspace's own `origin`:

```bash
GITHUB_REPO=$(git remote get-url origin 2>/dev/null)
TARGET_REMOTE="origin"
git fetch "$TARGET_REMOTE" wiki/init-scaffold 2>/dev/null && git ls-tree -r "$TARGET_REMOTE"/wiki/init-scaffold --name-only | grep "^wiki/{project-id}/"
```

If that returns anything, stop for the same reason — point the user at the open PR on that branch
(Step 11 shows how to find it) rather than re-scaffolding. If there's no `origin` remote configured
yet, this simply finds nothing to fetch — harmless, the local-directory check above is what
actually matters in that case.

## 2. Determine `project-id` and Project Name

In production this is **one repo, one project, one wiki** — the `project-id` is this project.
Derive it (kebab-case, e.g. `billing-export-service`) and its display name from `CLAUDE.md`'s
title, the same deterministic derivation `/init-code-wiki` uses — since both skills compute it
from the same source, it stays consistent with `code-wiki/{project-id}/` without needing to read
anything back from a shared file.

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

`/init-product-wiki` and `/init-code-wiki` share **one** fixed branch name, `wiki/init-scaffold`,
and one PR on it, so that `/wiki-ingest` (or whatever eventually writes code-wiki content) has a
single, unambiguous place to commit into later. Both skills simply target this constant name
directly; there's no shared state to read or originate first.

## 5. Create `wiki/SCHEMA.md` (only if it doesn't already exist)

This file is not per-project — it's written once for the whole `wiki/` tree and every project
under it follows the same schema. If `wiki/SCHEMA.md` already exists, skip this step entirely.

Write it with this exact content:

````markdown
# Product Wiki Schema & Conventions

This file defines conventions for every file under `wiki/{project-id}/`. Follow them precisely —
without a single enforced format, drift creeps in: inconsistent frontmatter, inconsistent
linking, inconsistent layout from one write to the next.

This is a **product wiki**: everything under `feature-requests/` is a *feature request* — a
capability proposed, being defined, or being changed — not a *feature* in the sense of code that
already exists. A separate codebase wiki (out of scope here) is where already-built system
architecture belongs; product-wiki pages never link into it.

In production this is **one repo, one project, one wiki** — `wiki/{project-id}/` is one full
instance of everything below.

---

## Current-State vs. Immutable-Ledger Discipline

Two kinds of file live here, with opposite update rules.

**Immutable ledger** (`decisions/DEC-*.md`): write-once. Never edited except adding a single
`superseded_by` field to an old decision when a later one explicitly supersedes it.

**Current-state** (most of `feature-requests/{id}/feature-request.md`: Current State, Key Facts,
Requirements, Business Rules, Open Questions, Risks, Relationships): represents *today's truth*,
not a history log. When a decision changes what's true, replace or trim the stale line and link
the `DEC-*` that changed it — never just append forever.

**Thin indexes** (`feature-request.md`'s `## Decisions`/`## Evidence` sections,
`feature-requests/index.md`, `decisions/index.md`): links and one-line pointers only. Never
restate a decision's `## Statement` in one of these — link to it instead.

---

## Slug & ID Formats

- Decision IDs: `DEC-NNNN`, sequential, zero-padded, per-project. Scan `decisions/DEC-*.md` for
  the current max and increment — never reuse or renumber once assigned. Filename is
  `DEC-NNNN_<kebab-case-slug-from-title>.md`; the `DEC-NNNN` prefix is what's authoritative for
  cross-references, the slug is a cosmetic, one-time label.
- Feature-request IDs: kebab-case, short, stable (e.g. `billing-export`). Treat renaming one as a
  breaking change to every link pointing at `feature-requests/{id}/`.

---

## `wiki/{project-id}/index.md` — project landing page

A short entry point that links out, not a raw content dump:

```markdown
# Wiki — <Project Name>

Last updated: <date>

- [Feature Requests](feature-requests/index.md) — what this project does, organized by capability
- [Decisions](decisions/index.md) — the full project-wide decision ledger
```

---

## `feature-requests/` — feature-request tree

One directory per feature request, created the first time a decision is confidently mapped to
it. Everything about a feature request lives in one file, `feature-request.md` — not split
across separate files.

### `feature-requests/index.md` — feature-request catalog

The first place to look to see "what does this project do" — one row per known feature request,
mapping to its `feature-requests/{feature-id}/feature-request.md`:

```markdown
# Feature Requests — <Project Name>

Last updated: <date>

| Feature Request | Summary | Status | Open Questions | Last Touched |
|---|---|---|---|---|
| [billing-export](billing-export/feature-request.md) | Billing export job and its trigger | active | 0 | <date> |
```

### `feature-requests/{feature-id}/feature-request.md`

```yaml
---
title: "Billing Export"
slug: billing-export
owners:
  - <owner name>
status: active   # active | deprecated
last_updated: <date>
---

## Current State
<Plain-language description of how this feature request works TODAY. Rewrite/trim as decisions
change it — not a running log of everything ever said about it.>

## Key Facts
- <Fact that holds today, linked to the DEC-NNNN that established it>

## Requirements
- <Requirement that holds today, linked to the DEC-NNNN that established it>

## Business Rules
- <Rule that holds today, linked to the DEC-NNNN that established it>

## Decisions
| Date | Title | Type | Ticket |
|---|---|---|---|
| <date> | [Title](../../decisions/DEC-NNNN_<slug>.md) | decided | [Linear](<url>) |

## Evidence
- [DEC-NNNN](../../decisions/DEC-NNNN_<slug>.md)

Links only, to `decisions/DEC-*.md` — never a copied excerpt of the transcript. The verbatim
quote already lives on the Decision Record's `evidence_quote` field; there is no separate
meeting page to link to instead (see "No Local Meeting Archive" below).

## Open Questions
- <Unresolved question>

**Resolved:**
- ~~<Former question>~~ → resolved by [DEC-NNNN](../../decisions/DEC-NNNN_<slug>.md)

## Risks / Rejected Approaches
- <Rejected approach or known risk, linked to the DEC-* that recorded it>

## Relationships
**Depends On:** <feature-id> — <one-line reason, linked to the DEC that established it>
**Related:** <feature-id> — <one-line reason>
```

Every section heading stays present even when empty — write "Nothing recorded yet." rather than
omitting it, so the next write has an obvious place to land. `## Decisions` and `## Evidence` are
thin indexes (links only); every other section is current-state.

---

## `decisions/` — canonical, project-wide decision ledger

The durable memory that answers "was this already decided / rejected / does it contradict
something" — project-wide, not per-feature-request, since two different feature requests can
still contradict or duplicate each other.

### `decisions/index.md` — flat ledger index

```markdown
# Decisions — <Project Name>

Last updated: <date>

| ID | Date | Title | Type | Feature Request | Ticket |
|---|---|---|---|---|---|
| [DEC-0001](DEC-0001_<slug>.md) | <date> | <title> | decided | [billing-export](../feature-requests/billing-export/feature-request.md) | [Linear](<url>) |
```

### `decisions/DEC-NNNN_<slug>.md` — one file per decision

One file per discussion item classified as Decided, Unresolved, Rejected, or Superseded. The
only classification that produces **no file** is `duplicate` — a reconciliation outcome (not a
classifier output) meaning this exact thing, with the same type, already exists.

```yaml
---
title: "Short decision title"
date: <date>
id: DEC-0001
feature: billing-export        # feature-request id, or null if no feature request matched
source_meeting: <slug>          # a label, not a file — no local meeting page exists to name
recording_id: <Drive file ID of the recording>    # this decision's only durable link back to the source meeting
transcript_id: <Drive file ID of the transcript>
type: decided                  # decided | unresolved | rejected | superseded
evidence_quote: "The verbatim line this decision is grounded in"
reconciliation:
  existed_before: false
  previously_rejected: false
  contradicts: []               # DEC-ids this conflicts with, if any
  on_roadmap: false
  dependencies: []               # DEC-ids or ticket ids this depends on
  changes_plan: false
supersedes: []                  # DEC-ids — only meaningful when type: superseded
linear_issue: null               # set to the issue URL once a real Linear ticket exists
---

## Statement
<The decision, one clear sentence>

## Reconciliation Notes
<1-3 sentences explaining why the reconciliation fields above were set the way they were>
```

**Status transitions**: a decision's `type` is never rewritten after creation except when a
*later* decision explicitly supersedes it — the old file gets `superseded_by: DEC-000N` added
(only then — it's absent otherwise, not pre-declared as `null`), the new file's
`supersedes: [DEC-000N]` points back. History stays intact.

---

## No Local Meeting Archive

There is no `archive/meetings/` directory and no per-meeting page under `wiki/{project-id}/`. A
meeting is a source event, not a durable artifact — its evidence lives inline on whichever
Decision Record(s) it produced (`recording_id`, `transcript_id`, `source_meeting`,
`evidence_quote`), not as a separately rendered page. A meeting-archive page would just be a
second copy of what the Decision Record and the feature's `## Key Facts` already hold.

## No Local Ticket Draft

A decision never gets a local ticket file. There is no `triage/` directory: a local draft ticket
would just duplicate content the Decision Record itself already holds (`## Statement`,
`evidence_quote`, `reconciliation`). A decision links straight to its real Linear issue
(`linear_issue`) once one exists; until then it leaves `linear_issue: null`.
````

## 6. Create `wiki/{project-id}/index.md`

```markdown
# Wiki — <Project Name>

Last updated: <date>

- [Feature Requests](feature-requests/index.md) — what this project does, organized by capability
- [Decisions](decisions/index.md) — the full project-wide decision ledger
```

## 7. Create `wiki/{project-id}/feature-requests/index.md`

Header row only — no feature requests exist yet:

```markdown
# Feature Requests — <Project Name>

Last updated: <date>

| Feature Request | Summary | Status | Open Questions | Last Touched |
|---|---|---|---|---|
```

## 8. Create `wiki/{project-id}/decisions/index.md`

Header row only — no decisions exist yet:

```markdown
# Decisions — <Project Name>

Last updated: <date>

| ID | Date | Title | Type | Feature Request | Ticket |
|---|---|---|---|---|---|
```

## 9. Confirm Before Pushing

Before touching git history or opening/updating a PR, show the user:
- the target repo (from Step 3) and branch name (`wiki/init-scaffold`, from Step 4)
- exactly what's about to be committed (`wiki/SCHEMA.md` if newly written, the
  `wiki/{project-id}/` tree)
- whether a PR will be **created** (no open PR found for this branch — see Step 11) or an existing
  one will simply gain a new **commit** (a PR for this branch already exists)

Get explicit go-ahead before proceeding — pushing and opening a PR are visible, shared-state
actions.

## 10. Branch, Commit, Push

```bash
git fetch "$TARGET_REMOTE"
git checkout wiki/init-scaffold 2>/dev/null || git checkout -b wiki/init-scaffold "$TARGET_REMOTE"/main 2>/dev/null || git checkout -b wiki/init-scaffold
git add wiki/SCHEMA.md wiki/{project-id}
git commit -m "chore: scaffold product-wiki directory structure for {project-id}"
git push -u "$TARGET_REMOTE" wiki/init-scaffold
```

## 11. Create or Reuse the PR

Check GitHub directly for an existing open PR on this branch — this is the authoritative check,
there's no local state file to consult:

```bash
gh pr list --repo "$REPO_SLUG" --head wiki/init-scaffold --state open --json url,number
```

- **If a PR is returned** — one already exists (opened by `/init-code-wiki` or a prior run).
  Nothing further to do; the commit just pushed lands on it automatically.
- **If none is returned** — this skill is the first of the two to reach this point. Create it:
  ```bash
  gh pr create --repo "$REPO_SLUG" --draft --title "Scaffold project wiki (code-wiki + product wiki)" --body "$(cat <<'EOF'
  ## Summary
  - Scaffolds wiki/SCHEMA.md and wiki/{project-id}/ (index.md, feature-requests/index.md, decisions/index.md — structure only, no content)
  - Long-lived scaffold PR: /wiki-ingest commits actual decisions/feature-requests here as they're written
  - Do not merge until the wiki has real content — this PR is the living wiki changeset

  🤖 Generated with [Claude Code](https://claude.com/claude-code)
  EOF
  )"
  ```

## 12. Report

Tell the user:
- `wiki/SCHEMA.md` was created (or already existed and was left untouched)
- `wiki/{project-id}/index.md`, `wiki/{project-id}/feature-requests/index.md`, and
  `wiki/{project-id}/decisions/index.md` are scaffolded and pushed
- The PR URL (whether newly created or already existing)
- No `DEC-*.md` or `feature-requests/{feature-id}/feature-request.md` files exist yet — those
  get written by `/wiki-ingest` the first time an actual decision or feature request exists,
  as additional commits on the same branch/PR
- This was a one-time onboarding step — running it again will stop at the Step 1 guard

---

## Rules

- This skill never writes `decisions/DEC-*.md` or `feature-requests/{feature-id}/feature-request.md`
  — that content-writing step belongs to `/wiki-ingest`, not this scaffold.
- Never create `archive/meetings/` or `triage/` under `wiki/{project-id}/` — see the note at the
  end of `wiki/SCHEMA.md` for why.
- `wiki/SCHEMA.md` is written once for the whole `wiki/` tree, never per-project — check it
  doesn't already exist before writing it.
- **One-time only.** Always check the working tree, and the shared branch if nothing's local,
  first (Step 1) — never re-scaffold if `wiki/{project-id}/` already exists either place.
- Share the branch and PR with `/init-code-wiki` — always check `gh pr list --repo "$REPO_SLUG"
  --head wiki/init-scaffold` before creating one; never open a second PR if one is already open.
- **The target repository is always this workspace's own `origin` remote** (Step 3) — resolve
  `$REPO_SLUG` from it and use `origin`, plus `gh --repo`, for every git/gh operation.
- Never invent a git remote URL — if `origin` isn't configured, ask the user for it.
- Always confirm with the user (Step 9) before pushing or creating a PR.
- Never overwrite an existing `wiki/{project-id}/` — guard first, stop if content is already there.
