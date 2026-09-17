---
name: wiki-init-generator
description: One-time orchestrator that runs /init-code-wiki and /init-product-wiki together as a single onboarding step, since both already share one branch and one PR. Use this instead of running each skill separately.
disable-model-invocation: true
allowed-tools:
  - Read
  - Write
  - Glob
  - Bash
---

# Wiki Init Generator

Orchestrates the two wiki-scaffold onboarding skills — `/init-code-wiki` (scaffolds `code-wiki/`) and
`/init-product-wiki` (scaffolds `wiki/`) — so a user runs one command instead of two. Both skills already
know how to share one fixed branch name (`wiki/init-scaffold`) and check GitHub directly for an existing
PR on it; this skill just sequences them and reports combined status. It writes no content itself.

## 1. Guard — What's Already Scaffolded?

```bash
find code-wiki/{project-id} -maxdepth 1 -type d 2>/dev/null
find wiki/{project-id} -maxdepth 2 -name "*.md" 2>/dev/null
```

- If both come back populated (code-wiki has `Architecture`/`Features`/`Schemas`, wiki has
  `index.md`/`feature-requests/index.md`/`decisions/index.md`), **stop** — tell the user both wikis
  are already scaffolded and this is a one-time onboarding step, not a recurring one.
- If only one is populated, skip straight to running the missing half (Step 3).
- If neither is populated locally, also check the shared branch before assuming a fresh start (in
  case it scaffolded there but isn't merged/checked out here):
  ```bash
  git fetch origin wiki/init-scaffold 2>/dev/null && git ls-tree -r origin/wiki/init-scaffold --name-only | grep -E "^(code-wiki|wiki)/{project-id}/"
  ```
  Treat anything found there the same as finding it locally.
- If genuinely nothing is found anywhere, run both (Step 2 then Step 3).

## 2. Run `/init-code-wiki`

Follow the `init-code-wiki` skill instructions (`.claude/skills/init-code-wiki/SKILL.md`) in full,
including its own Guard, its confirm-before-push step, and its branch/commit/push/PR steps.

If the user declines or stops at its confirmation step, stop here too — do not proceed to
`/init-product-wiki` without the first half landing (or being deliberately skipped by the user).

Skip this step entirely if Step 1 already found the code-wiki scaffolded.

## 3. Run `/init-product-wiki`

Follow the `init-product-wiki` skill instructions (`.claude/skills/init-product-wiki/SKILL.md`) in
full, including its own Guard and confirm-before-push step. Its own `gh pr list --head
wiki/init-scaffold` check (its Step 11) finds the PR Step 2 just opened, if any, and adds a commit
to it rather than opening a new one.

Skip this step entirely if Step 1 already found the product wiki scaffolded.

## 4. Report

Tell the user:
- Which of the two scaffolds were newly created vs. already present going in
- The shared branch name (`wiki/init-scaffold`) and PR URL (from whichever step's `gh pr create`/
  `gh pr list` output surfaced it)
- That both trees are now scaffolded
- This was a one-time onboarding step — re-running `/wiki-init-generator` will stop at the Step 1 guard

---

## Rules

- Never run `/init-code-wiki` or `/init-product-wiki` a second time if Step 1 already found its
  tree scaffolded — check Step 1 first, and re-check before Step 3 in case Step 2 already
  satisfied both (unlikely, but cheap to confirm).
- Both halves share one branch and one PR — never let either open a second PR; each skill's own
  `gh pr list --head wiki/init-scaffold` check is what prevents that.
- Still let each skill run its own confirmation gate before it pushes or opens a PR — this
  orchestrator does not skip or merge those confirmations into one.
- If either skill asks for a repository URL because `origin` isn't configured, relay that prompt to
  the user rather than guessing one.
- This skill writes no content of its own — everything it produces comes from following the two
  skills it wraps.
