---
name: linear-implement-trigger
description: Poll Linear for tickets a human has moved out of Triage into the ready-to-build state, and trigger /implement on each one not already triggered. Meant to run on a recurring schedule, not invoked ad hoc.
disable-model-invocation: true
allowed-tools:
  - Read
  - Write
  - Edit
  - Glob
  - Grep
  - Bash
  - Task
  - AskUserQuestion
---

# Linear Triage-Exit Poller: /linear-implement-trigger

Every ticket `wiki-ticket-creator.md` files (via `/wiki-ingest`, live `WIKI_TICKET_MODE`) lands in
Linear's **Triage** status by design, so a human reviews it before any code gets written. This
skill watches for tickets a human has since moved *out* of Triage into the project's
ready-to-build state, and triggers `/implement <ticket-id>` on each one not already triggered —
scoped to **every** ticket reaching that state, not just meeting-sourced ones.

`disable-model-invocation: true` for the same reason `implement/SKILL.md` sets it: this can spawn
a full, unattended `/implement` run against a real ticket. The one difference from that skill —
documented in `implement/SKILL.md`'s own header — is that once a human has explicitly set
`IMPLEMENT_POLL_ENABLED=true` and registered this skill on a schedule, a scheduled invocation
follows `implement/SKILL.md`'s instructions **directly inline** for each newly-ready ticket, rather
than invoking `/implement` as a nested Skill-tool call.

---

## 1. Load Config

Read `.claude/wiki-project.env`. Fields used: `LINEAR_TEAM_KEY`, `LINEAR_READY_STATE` (default
`Todo` if unset), `IMPLEMENT_POLL_ENABLED`.

## 2. Guard — Is Polling Enabled?

If `IMPLEMENT_POLL_ENABLED` is not exactly `true`, **stop**. Tell the user:

> Linear polling is off (`IMPLEMENT_POLL_ENABLED=false` in `.claude/wiki-project.env`). Flip it to
> `true` when you're ready, and register this skill on a recurring schedule (`/schedule` or the
> `CronCreate` tool) — running it once ad hoc doesn't give you continuous polling.

Never proceed past this guard just because the skill was invoked — the flag is the one thing that
turns this from a manual check into standing automation, and it must be a deliberate, human
choice.

## 3. Query Linear for Ready Tickets

Use the `claude.ai Linear` MCP tools (`list_issues`) to fetch every issue in `LINEAR_TEAM_KEY`
currently in the `LINEAR_READY_STATE` status. If `LINEAR_TEAM_KEY` isn't set, **stop** and tell
the user to set it in `.claude/wiki-project.env` first (it's normally written by
`wiki-ticket-creator.md` the first time it files a live ticket, or by `/init-project-structure`).

## 4. Filter to Not-Already-Triggered

For each ticket returned, check whether it's already been triggered:

```bash
find docs/execution -maxdepth 1 -type d -name "<TICKET_ID>-*"
```

- **Found** — `/implement` already created this ticket's execution folder on a prior run (its own
  idempotency signal), so this ticket has already been triggered at least once, however far it's
  progressed since. Skip it — `/implement` itself is resumable, and a human drives every later
  pause point manually with `/implement <ticket-id>`, not this poller.
- **Not found** — this is a genuinely new ready ticket. Proceed to Step 5 for it.

## 5. Trigger `/implement` Inline, Per New Ticket

For each new ticket, in turn: follow `implement/SKILL.md`'s instructions directly inline, starting
from its **State Resolution** step (§2) with this `TICKET_ID` — a fresh start, since no execution
folder exists yet. Let it run through to whatever phase it naturally stops at
(`REQUIREMENTS` almost always pauses immediately for clarifications, per its own phase table) —
**never force it past a phase that skill itself says to stop at**, even though this poller reached
it automatically rather than via a typed `/implement` command.

Process tickets one at a time, not concurrently — `implement/SKILL.md` assumes it owns the
terminal/session context for the duration of a phase; running several inline at once would
interleave their state confusingly.

## 6. Report

Tell the user, for this run:
- How many ready tickets were found in `LINEAR_READY_STATE`
- How many were already triggered (skipped) vs. newly triggered
- For each newly-triggered ticket: which phase `/implement` stopped at and what it's waiting on

---

## Rules

- **Never trigger anything if `IMPLEMENT_POLL_ENABLED` isn't `true`** — this is the single most
  important guard in this skill.
- **Once-per-ticket-ever**: the existence of `docs/execution/{TICKET_ID}-*/` is the only
  idempotency check — never re-trigger a ticket that already has one, even if it's sitting at an
  early, seemingly-stalled phase. A human resumes those manually via `/implement <ticket-id>`.
- Never advance a triggered ticket past a phase `implement/SKILL.md` itself says to stop at —
  this poller's job is only to *start* `/implement` for new tickets, not to auto-approve plans,
  clarifications, or reviews on their behalf.
- Process newly-ready tickets sequentially, never in parallel.
- This skill has no effect without being registered on a recurring schedule — running it manually
  once just performs a single poll pass, which is fine for testing but isn't "polling."
