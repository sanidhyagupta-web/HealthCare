---
name: closeout-feat-recorder
description: Record delivered reality into this repository's own code-wiki (code-wiki/**) from a PR's delivered diff, at closeout time — after review passes clean, immediately before the PR is marked ready for human review. Writes the FEAT for a feature ticket, before/after evidence for a bug, or an ADR plus the affected FEAT for tech debt. Commits to the branch already checked out; never pushes, never touches Linear or the PR. Unconditional on whatever the deviation-check sortie decides afterward — reality is recorded either way.
disable-model-invocation: true
allowed-tools:
  - Read
  - Write
  - Edit
  - Glob
  - Grep
  - Bash
---

# closeout-feat-recorder

The code-wiki's per-ticket upkeep step `update-feature-registry`'s own banner says does not exist
yet. It does now, and it runs post-merge-readiness rather than by hand: `runCloseout`
(`apps/server/src/activities/closeout.ts`) invokes this skill from a container sandbox, on the
PR's own head branch, right after review passes clean and right before
`markPrReadyForHumanReview`.

**Container-only.** This skill needs `Bash` to commit with `git`, which the caller (`runCloseout`)
only ever grants inside the sandbox container — never on the CLI boundary. If you are reading this
outside a container, something upstream misconfigured the run; stop rather than proceeding.

**You have no `git diff` to run yourself.** The delivered diff is already computed and written to
disk by the caller — its path is given to you in the invocation. Read it; do not attempt to derive
it yourself from `git log`/`git diff` against a base branch you cannot independently resolve.

## Args

Exactly: a ticket identifier, its resolved `work-type` (`feature`/`bug`/`tech_debt` — already
decided by the caller; never re-derive it independently), the path to the delivered diff, and the
delivered diff's own content hash (for the commit trailer, Step 3).

Example: `/closeout-feat-recorder AI-123, work-type feature, delivered diff at
.flightdeck/closeout/delivered.patch`

## 1. Read the delivered diff

Read the file at the given path. It is a unified diff (`git diff <base>...<head>` output) — the
full set of changes this PR delivers, not a summary. Read the current `code-wiki/**` tree too
(`Glob`/`Read`), so a write below updates existing pages rather than duplicating them.

If the tree does not exist yet at all (no `/init-code-wiki` has ever run for this project), stop
and say so — this skill updates an existing code-wiki, it does not scaffold one.

## 2. Write, by work type

- **`feature`** — write or update the FEAT page(s) the delivered diff actually touches
  (`Features/Feat-NNNN-*/Index.md`), from what the diff shows was built, not from what the ticket
  asked for. A diff that implements less than the ticket, or differently, is recorded as what it
  is — this skill records reality, it does not reconcile it against intent (that is the
  deviation-check sortie's job, run separately, after this one).
- **`bug`** — write the same FEAT update, plus explicit before/after evidence (what broke, what the
  diff changes about it) in the affected feature's own page. Never write a new roadmap-shaped
  feature request for a bug fix.
- **`tech_debt`** — write a short ADR-style note (what changed structurally and why) plus an update
  to whichever FEAT page(s) the change affects. Never a new feature page for tech debt alone.

Never touch anything outside `code-wiki/**`. Never write to `wiki/**` — that tree is intent, this
one is reality, and duplicating one into the other is the mistake v4-DEC-021 exists to prevent.

## 3. Commit — never push

```bash
git add code-wiki/
git commit -m "$(cat <<'EOF'
<ticket-id>: record delivered reality (closeout)

Ticket: <ticket-id>
Closeout-Delivered-SHA: <the delivered-diff hash given to you>
Closeout-Kind: <feature|bug|tech_debt>
EOF
)"
```

The three trailers are load-bearing: `runCloseout`'s own idempotency guard reads them back out of
git history on every future run for this ticket, scoped to this PR's own head commit, never
`git log --all` — an identical `Closeout-Delivered-SHA` on a later re-run means "nothing new was
delivered," and both this skill and the deviation-check sortie are skipped that time.

**Do not push. Do not open or touch a pull request. Do not write to Linear.** The caller pushes
this commit itself, onto the PR's own head branch, after this skill (and, separately, the
deviation-check sortie) finish.

## 4. Report

End your final message with a one-line summary of what was recorded (which page(s), which
work-type path taken) — this is corroboration for the caller's own log, never the caller's
evidence that a commit exists. `runCloseout` verifies the commit itself, from `git`, not from this
line.
