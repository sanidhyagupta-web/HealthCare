---
name: wiki-ingest
description: Process new meeting recordings (Google Drive or local fixtures) into this project's product wiki — decisions, feature requests, tickets, and a PR. The "temporal agent" that owns run-state.json and drives every unprocessed item through the full pipeline, idempotently.
argument-hint: "[local|drive]"
allowed-tools:
  - Read
  - Write
  - Edit
  - Glob
  - Grep
  - Bash
  - AskUserQuestion
---

# Meeting Wiki Pipeline Orchestrator: /wiki-ingest

You are the "temporal agent" for this project's product wiki: the one thing that turns meeting
recordings into durable, feature-centric knowledge (`wiki/{project-id}/`) and, from there, real
tickets. Every other `wiki-*.md` file in this directory is a stateless step you `Read` and follow
directly — none of them are typed as slash commands, and none of them own retry/cost/idempotency
state. That's all here.

This project's wiki is **single-project, single-repo**: there is no `projects-registry.json` and
no project-mapping/onboarding step. Everything under `wiki/{project-id}/` belongs to this one
project, whose identity comes from `.claude/wiki-project.env`.

---

## 1. Load Project Config

Read `.claude/wiki-project.env`. If it doesn't exist, **stop** — tell the user to run
`/init-project-structure` (or manually create the file per `docs/ONBOARDING.md`) before this can run.

Fields used by this pipeline: `WIKI_PROJECT_ID`, `WIKI_PROJECT_NAME`, `WIKI_PROJECT_ALIASES`,
`WIKI_TICKET_MODE`, `WIKI_PUBLISH_MODE`, `LINEAR_TEAM_KEY`, `LINEAR_PROJECT_ID`, `GITHUB_REPO`,
`DRIVE_FOLDER_ID`.

## 2. Guard — Has the Wiki Been Scaffolded?

```bash
find "wiki/$WIKI_PROJECT_ID" -maxdepth 2 -name "*.md" 2>/dev/null
```

If nothing is found, **stop** — tell the user to run `/init-product-wiki` first. This skill only
ever writes *content* into an already-scaffolded tree; it never creates `wiki/SCHEMA.md` or the
initial `index.md` files itself.

## 3. Determine Source

`$ARGUMENTS` is `local` or `drive`. If omitted: use `drive` if `DRIVE_FOLDER_ID` is set in
`.claude/wiki-project.env`, otherwise `local`.

- `local` — scans `inbox/` at the repo root for fake meeting drops (fixtures for testing the
  pipeline without touching Drive).
- `drive` — scans the Google Drive folder at `DRIVE_FOLDER_ID` for real Gemini meeting notes.

## 4. Load / Initialize `run-state.json`

`run-state.json` (repo root, **git-ignored** — add it to `.gitignore` if not already there) is
transient: it only needs to survive a crash *within* one run, so the next invocation resumes from
an item's last completed phase instead of restarting the whole run. It is not the durable
idempotency ledger — that's `wiki/{project-id}/processed.json` (Step 6).

```json
{
  "run_started": "<ISO timestamp>",
  "source": "local",
  "cost_limit_usd": 5.00,
  "cost_spent_usd": 0.00,
  "max_retries_per_item": 2,
  "items": {
    "<item-id>": { "status": "pending", "phase": null, "retries": 0 }
  }
}
```

If a `run-state.json` from a previous, incomplete run exists with items still `pending` or
`in_progress`, resume it rather than starting fresh — pick up each such item at its recorded
`phase`. If `cost_limit_usd`/`max_retries_per_item` aren't customized elsewhere, use the defaults
above.

## 5. Phase A — Scan

Follow `wiki-local-scanner.md` or `wiki-drive-scanner.md` (per Step 3), reading
`wiki/{project-id}/processed.json` first so already-processed items are skipped. This produces a
list of unprocessed items, source-agnostic in shape from here on.

If the list is empty: report "up to date, no new recordings" and **stop** — do not touch
`run-state.json` further.

Otherwise, add each new item to `run-state.json`'s `items` map with `status: "pending"` before
continuing.

## 6. Per-Item Pipeline

For each unprocessed item, **in order**, unless `cost_spent_usd` has already reached
`cost_limit_usd` (in which case stop starting NEW items — finish whatever's already
`in_progress`, then go to Step 8):

Mark the item `in_progress` in `run-state.json` and drive it through every phase below, updating
`phase` after each one completes so a crash mid-item resumes correctly:

1. **(Drive source only)** `wiki-transcript-reader.md` — clean the raw VTT/SRT into text. Local
   fixtures already are text; skip straight to 2.
2. `wiki-sanitizer.md` — strip unsafe markup, redact secrets, enforce the size cap, wrap as
   `[EVIDENCE]`.
3. `wiki-relevance-checker.md` — is this item actually about `WIKI_PROJECT_NAME` (or one of
   `WIKI_PROJECT_ALIASES`)? Below the confidence threshold: mark this item
   `status: "not_relevant"` in `wiki/{project-id}/processed.json`, log it, and move to the next
   item — no further phases run, no file gets written, this is not a failure.
4. `wiki-summarizer.md` — extract decisions, action items, key facts, feature-matching hints.
5. `wiki-decision-classifier.md` — tag each item `decided` / `unresolved` / `rejected` /
   `superseded`.
6. `wiki-feature-mapper.md` — match against `feature-requests/index.md`. If unmatched but flagged
   `new_feature_candidate`/`possible_alias_of`, run `wiki-feature-onboarder.md` — **always asks
   the user, never automatic**. If genuinely no signal, proceed with `feature: null` (still gets a
   decision file — that field is the only record).
7. `wiki-conflict-detector.md` — reconcile against this project's **entire** `decisions/` history
   (every feature, not just the mapped one): existed before? previously rejected? contradicts
   something? on the roadmap? dependencies? changes an existing plan? This step is authoritative —
   it can upgrade/downgrade the raw classification from step 5, including to `duplicate`.
8. **If conflicts were found:** `wiki-resolution-handler.md` — pause, ask the user, one conflict
   at a time.
9. `wiki-writer.md` — write `decisions/DEC-NNNN_<slug>.md` and update the mapped feature's
   `feature-requests/{id}/feature-request.md`. Skip entirely if step 7 resolved to `duplicate` —
   no decision file, no ticket, for that outcome only.
10. `wiki-index-updater.md` — surgical updates to `feature-requests/index.md` and
    `decisions/index.md`.
11. `wiki-ticket-creator.md` — one ticket per decision written (every type except `duplicate`,
    which never reaches here since step 9 skipped it).

**If any phase fails:** retry that phase up to `max_retries_per_item` times. If still failing,
mark the item `status: "failed"` in `run-state.json`, log the error, and move to the next item —
one item's failure never aborts the run.

**On success:** record the item in `wiki/{project-id}/processed.json` (durable, forever — this is
what makes re-running the same source a no-op for anything already seen) and set
`status: "done"` in `run-state.json`.

## 7. Publish

After every item in this run has reached `done`/`failed`/`not_relevant`, if any wiki files
actually changed, follow `wiki-github-publisher.md` **once** for the whole run (not once per
item) — it always pauses and asks for explicit approval before doing anything, in either
`WIKI_PUBLISH_MODE`.

## 8. Report

Tell the user, for this run:
- Items scanned, and how many were new
- Per-item outcome: `done` (with decision type), `not_relevant`, or `failed` (with the error)
- Decisions written, by type, and which feature requests they touched (new features created via
  `wiki-feature-onboarder.md` called out explicitly)
- Tickets: real Linear links (`WIKI_TICKET_MODE=live`) or the pending list (`draft`)
- Publish outcome: PR URL / commit landed, `PENDING_PUBLISH.md` entry, or skipped by user

---

## Error Handling

- A phase failure retries in place (Step 6) before the item is marked `failed` — never silently
  skip a phase.
- One item's `failed` status never blocks or aborts processing of other items in the same run.
- Hitting `cost_limit_usd` stops **new** items from starting but lets already-`in_progress` items
  finish their current phase cleanly — never abandon an item mid-phase over cost.
- `run-state.json` surviving between invocations is what makes a crashed run resumable — never
  delete it except when a run completes with all items in a terminal state (`done`/`failed`/
  `not_relevant`).

## Rules

- `wiki/{project-id}/processed.json` is the durable idempotency ledger — check it in Step 5
  before including any item as "new."
- `run-state.json` is git-ignored, transient, and per-run — never treat it as a substitute for
  `processed.json`.
- Never skip the relevance check (Step 6.3) — an item's source being in this project's `inbox/`
  or Drive folder does not by itself make it about this project.
- `wiki-github-publisher.md` always asks before doing anything, regardless of `WIKI_PUBLISH_MODE`
  — never bypass its confirmation because "this run already got permission earlier."
- Every sub-skill file listed here is a flat `.md` file directly under `.claude/skills/` — `Read`
  and follow it, never invoke it as a slash command.
