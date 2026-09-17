---
name: create-prs
description: Push a branch to remote and open or update its pull request, for any kind of work — reads execution-state.md when present, otherwise derives everything from the branch's own commits and diff.
disable-model-invocation: true
---

# Push & Create Pull Requests

Push a feature branch and open its PR — or update the PR if one is already open. Works for any
work on a branch: implementation, documentation, wiki entries, scaffolding. The branch is the
input; what produced it does not matter.

## Prerequisites
- The work is committed on the branch. Nothing here writes content.
- For human-driven implementation flows: checks pass, user approved, CLAUDE.md updated.

## Steps

### 1. Establish context

Two sources, in order of preference.

**If `execution-state.md` exists**, read it for branch names and the task list. This is the
implementation flow's own record and is richer than anything the branch can tell you — prefer it
whenever it is there.

**Otherwise, derive everything from the branch.** Determine the base branch (the repo's default
branch unless told otherwise), then:

```bash
BASE=$(gh repo view --json defaultBranchRef -q .defaultBranchRef.name)
git log --format='%s%n%b' "origin/$BASE..HEAD"   # what was done, in the author's words
git diff --stat "origin/$BASE...HEAD"            # scope
git diff --name-only "origin/$BASE...HEAD"       # which files
```

Commit messages are the primary evidence of intent; the diff tells you scope and which components
were touched. Together they are enough to write a description — do not go looking for a ticket
tracker or planning documents that may not exist in this flow.

If the branch name embeds a ticket id (`wiki/AI-124`, `feature/AI-124-thing`), use it for the PR
title prefix and the tracker link in step 4. If it does not, omit both rather than inventing one.

### 2. Push

```bash
git push -u origin {branch-name}
```

### 3. Open or update the pull request

**Check first — a PR may already exist.** Every round of an iterative flow reaches this step, and
`gh pr create` fails against a branch that already has an open PR.

```bash
gh pr list --head {branch-name} --state open --json number,url,isDraft
```

**No open PR — create one.** Add `--draft` when the caller asked for a draft (see *Draft PRs in
automated flows*):

```bash
gh pr create --title "{TICKET-ID}: {Short summary}" --body "$(cat <<'EOF'
## Summary
- {2-4 bullet points}

## Changes
### {Service/App/area name}
- {Key files and what changed}

## Testing
- {Tests run and results, or "n/a — documentation only"}

## References
- **Ticket**: {ticket ID, if known}
{Planning document links, only if those files exist}

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

**A PR already exists — update it** so the description reflects everything on the branch now, not
just this round's commits:

```bash
gh pr edit {PR_NUMBER} --title "..." --body "$(cat <<'EOF'
...same structure, rewritten from the full branch history...
EOF
)"
```

Rewrite the body from the whole branch, not by appending. An accreted list of per-round notes is
harder to review than one current description, which is the point of a PR body.

### 4. Link to the ticket tracker (if there is one)

If a ticket id is known *and* a tracker MCP tool is available, attach the PR URL — for Linear,
`save_issue` or a comment. Skip silently when either is missing; not every flow has a ticket.

### 5. Update execution state (only if it exists)

If you read `execution-state.md` in step 1, set status to `PR_CREATED` and record the PR URLs.
Skip this step entirely in branch-derived mode — do not create the file.

### 6. Report

PR link, one-line summary, and whether it was created or updated.

## Draft PRs in automated flows

Opening the PR as a draft is the right default **only** when something later marks it ready — an
automated review pass, a CI gate, a headless loop. A draft signals "not yet worth a human's
attention", and a PR nobody un-drafts is a PR nobody reviews.

**The caller states which mode applies.** Do not infer it from whether `execution-state.md`
existed — those are unrelated questions.

**Human-driven work:** no `--draft`. That is the default above.

**Automated flows:** pass `--draft` on create, and have the automation flip the PR when its loop
finishes:

```bash
gh pr ready {PR_NUMBER}
```

Flip on **every** terminal state, not just the clean one. A run that timed out, exhausted its
budget, or escalated is equally done and equally needs human eyes — restricting the flip to the
success path leaves failed runs stuck in draft indefinitely, which is the exact outcome draft
status is supposed to prevent.

`gh pr ready` is idempotent, so a retried step will not fail on an already-ready PR. Note that the
REST API has no "undraft" endpoint; `gh` uses the GraphQL `markPullRequestReadyForReview` mutation
underneath, which matters if you are calling the API directly rather than shelling out to `gh`.

## Rules
- Always push with `-u`
- Do NOT force push
- One PR per repository with changes
- PR title follows the repo's commit format
- Do not merge — that is a human's decision
- Never write or amend content here; this skill publishes what is already committed
