# wiki-github-publisher

Publishes this run's wiki changes (decisions, feature-request edits, index updates) onto the
shared `wiki/init-scaffold` branch/PR — the same branch `/init-product-wiki` and `/init-code-wiki`
scaffold, so wiki content lands as additional commits on one long-lived PR rather than a new PR
per run.

## Input

Every file changed by `wiki-writer.md`/`wiki-index-updater.md`/`wiki-ticket-creator.md` in this
run, plus `GITHUB_REPO` from `.claude/wiki-project.env`.

## Step 0 — Always Ask First

**Regardless of `WIKI_PUBLISH_MODE`, always stop and ask the user before doing anything** —
including before writing the draft-mode `PENDING_PUBLISH.md` entry. This is not skippable because
"it's just draft mode" or "the user already approved publishing earlier in this run" — every
project, every invocation of this step, gets asked explicitly. Show exactly which files changed.

## Steps

1. **Resolve the target repository**, same pattern `/init-product-wiki` uses: `GITHUB_REPO` from
   `.claude/wiki-project.env` if set, otherwise this workspace's own `origin`. Never invent a
   remote URL — ask the user if neither is configured.
   ```bash
   GITHUB_REPO=$(grep '^GITHUB_REPO=' .claude/wiki-project.env 2>/dev/null | cut -d= -f2-)
   [[ -z "$GITHUB_REPO" ]] && GITHUB_REPO=$(git remote get-url origin 2>/dev/null)
   REPO_SLUG=$(echo "$GITHUB_REPO" | sed -E 's#^(https://github\.com/|git@github\.com:)##; s#\.git$##')
   TARGET_REMOTE=$(git remote -v | awk -v url="$GITHUB_REPO" '$2 == url || $2 == url".git" {print $1; exit}')
   [[ -z "$TARGET_REMOTE" ]] && TARGET_REMOTE="wiki-target"
   ```

2. **If `WIKI_PUBLISH_MODE == "draft"`:** append an entry to `wiki/{project-id}/PENDING_PUBLISH.md`
   describing what would be pushed (file list, one-line summary per decision/feature touched) —
   no `git`/`gh` call at all. Report this to the user and stop.

3. **If `WIKI_PUBLISH_MODE == "live"`:** re-confirm the exact repo and branch with the user before
   touching git — a second, more specific confirmation than Step 0, right before the actual
   commands run.

4. **Check for an existing scaffold PR directly on GitHub** — no local state file to consult, this
   is the authoritative check (same convention `/init-product-wiki`/`/init-code-wiki` use):
   ```bash
   gh pr list --repo "$REPO_SLUG" --head wiki/init-scaffold --state open --json url,number
   ```
   - **PR found** — check out `wiki/init-scaffold`, commit this run's changes, push. The commit
     lands on the existing PR automatically.
   - **No PR found** — this shouldn't normally happen (the branch/PR should already exist from
     `/init-product-wiki`/`/init-code-wiki`), but if it does, create the branch off the target
     repo's default branch, commit, push, and open the PR the same way those onboarding skills do.

5. **Commit and push:**
   ```bash
   git fetch "$TARGET_REMOTE"
   git checkout wiki/init-scaffold 2>/dev/null || git checkout -b wiki/init-scaffold "$TARGET_REMOTE"/main
   git add "wiki/$WIKI_PROJECT_ID"
   git commit -m "wiki: process $(date -u +%Y-%m-%d) meeting ingest run"
   git push "$TARGET_REMOTE" wiki/init-scaffold
   ```

## Output

The PR URL (existing or newly created), or the `PENDING_PUBLISH.md` entry text (draft mode), or
`skipped_by_user` (logged, not an error) if the user declines at Step 0.

## Rules

- **Step 0's confirmation is never skippable**, in either mode, for any reason.
- Live mode is **always a PR** — never a direct push to the repo's default branch.
- Never open a second PR for `wiki/init-scaffold` — the `gh pr list` check in Step 4 is what
  prevents that; trust it over any local assumption about whether a PR "should" already exist.
- `GITHUB_REPO` (from `.claude/wiki-project.env`) is the source of truth for the target repo —
  never cross-check it against this workspace's own `origin` or refuse to proceed because they
  differ.
- A user decline at Step 0 is a normal, loggable outcome (`skipped_by_user`) — not an error to
  retry or work around.
