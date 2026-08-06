---
name: init-code-wiki
description: One-time onboarding scaffold of the code-wiki directory skeleton — code-wiki/{project-id}/Architecture/, Features/, and Schemas/ — pushed as a PR to the project's repository. Creates empty directories (with .gitkeep placeholders) plus the static SCHEMA.md doc-format contract; no scan-derived content. Shares one branch/PR with /init-product-wiki so a Temporal Agent can later commit wiki content into the same PR.
disable-model-invocation: true
allowed-tools:
  - Read
  - Write
  - Glob
  - Bash
---

# Init Code Wiki

Scaffold the empty directory skeleton for a project's **code-wiki** — the codebase-derived
documentation tree (architecture, features, schemas), as opposed to the product-derived `wiki/`
created by `/init-product-wiki` (decisions and feature *requests*). **This skill creates
directories** (plus a `.gitkeep` per directory so git can track them) **plus `SCHEMA.md`** — the
one piece of code-wiki content that's static rather than scan-derived, so there's no reason to
defer it (same reasoning `/init-product-wiki` already applies to `wiki/SCHEMA.md`). It never
writes `Architecture/Overview.md`, `Schemas/schemas.md`, or any
`Features/Feat-NNNN-{feature-id}/Index.md` — those genuinely require a codebase scan and are
written later, by `/init-feature-registry`, the first time it documents architecture, a feature,
or a schema.

**This is a one-time onboarding step.** It runs once per project, ever — see the Guard below and
`docs/ONBOARDING.md`, which points to this skill as part of first-time setup.

## The Target Shape (context only — not created by this skill)

Once populated by later skills/agents, a project's code-wiki looks like this:

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

**`Features/`** — every feature documented by `/init-feature-registry` lives here as its own
`Feat-NNNN-{feature-id}/` folder. This skill never creates that example folder — `Features/` stays
empty until a real feature is documented.

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

No `Overview.md`, no `schemas.md`, no example `Feat-*` folder — those require an actual codebase
scan and stay deferred to `/init-feature-registry`. Git does not track empty directories, so each
gets a bare `.gitkeep` — that placeholder exists purely so the folder survives a commit; it carries
no content and later skills should leave it in place (a directory that gains real files no longer
needs it removed, it's simply harmless).

## 1. Guard — Has This Already Run?

This scaffold may live on the shared `wiki/init-scaffold` branch and not yet be merged to `main`,
so check both places before concluding it hasn't run.

Check the current branch's working tree first:

```bash
find code-wiki/{project-id} -maxdepth 1 -type d 2>/dev/null
```

If that finds `Architecture`, `Features`, and `Schemas` already, **stop** — tell the user the
code-wiki was already scaffolded and this skill is a one-time onboarding step, not a recurring one.

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
and one PR on it — so a later content-writer (`/wiki-ingest`, `/init-feature-registry`, etc.) always
has a single, unambiguous place to commit into. Both skills simply target this constant name
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

Then write `code-wiki/{project-id}/SCHEMA.md` — **only if it doesn't already exist** (an earlier
`/init-feature-registry` run may have written it inline, per that skill's own guard):

````markdown
# Code Wiki Schema

Documentation-format contract for this project's `code-wiki/`. Don't restate content that
belongs in `docs/features/` (business rules, invariants — that's the AI-context source of
truth); this tree is the human-readable rendering of the same underlying facts.

## Features/Feat-NNNN-{feature-id}/Index.md
- `Feat-NNNN` is assigned once per feature, by scanning existing `Feat-NNNN-*` directories for the
  current max and incrementing — never renumber an existing directory.
- Sections: Overview, Domain Purpose, Key Flows, Business Rules (prose, not the AI-context
  table), Entities (link to `Schemas/schemas.md#{table}`, don't restate columns), Recent Changes.

## Architecture/Overview.md
- System topology, tech stack per layer, cross-cutting architectural decisions (only ones
  recurring across 2+ features — a single feature's own decision lives in that feature's file
  instead), coupling graph.

## Schemas/schemas.md
- One row per entity, full column/constraint detail, owning `Feat-NNNN`, cross-feature FKs.
  Written once here — never duplicated per-feature.
````

## 6. Confirm Before Pushing

Before touching git history or opening/updating a PR, show the user:
- the target repo (from Step 3) and branch name (`wiki/init-scaffold`, from Step 4)
- exactly what's about to be committed (`code-wiki/{project-id}/SCHEMA.md` if newly written, plus
  the rest of the `code-wiki/{project-id}/` tree)
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
- `code-wiki/{project-id}/Architecture/`, `Features/`, and `Schemas/` are scaffolded and pushed
- `SCHEMA.md` was created (or already existed and was left untouched)
- The PR URL (whether newly created or already existing)
- No scan-derived content was written — `Architecture/Overview.md`, `Schemas/schemas.md`, and
  every `Features/Feat-NNNN-{feature-id}/Index.md` get written later by `/init-feature-registry`
  the first time it documents architecture, a feature, or a schema, as additional commits on the
  same branch/PR
- This was a one-time onboarding step — running it again will stop at the Step 1 guard

---

## Rules

- This skill only ever writes `SCHEMA.md` under `code-wiki/{project-id}/` — it's static, not
  scan-derived, so writing it here doesn't require reading any code. Everything else stays
  directories plus `.gitkeep` only.
- Never write `Architecture/Overview.md` or `Schemas/schemas.md`, and never create an
  example/placeholder `Feat-0001-{feature-id}/` folder — those require an actual codebase scan and
  belong to `/init-feature-registry`; `Features/` stays empty until a real feature is documented.
- Skip writing `SCHEMA.md` if it already exists (e.g. an earlier `/init-feature-registry` run
  wrote it inline) — never overwrite it.
- **One-time only.** Always check the working tree, and the shared branch if nothing's local,
  first (Step 1) — never re-scaffold if `code-wiki/{project-id}/` already exists either place.
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
