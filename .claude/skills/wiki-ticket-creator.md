# wiki-ticket-creator

Creates one ticket per decision `wiki-writer.md` actually wrote — every type except `duplicate`
(which never reaches here, since `wiki-writer.md` skipped it entirely). No further gate: a
decision reaching this step always gets a ticket, framed per its type.

## Input

`{ dec_id, reconciled_type, decision_file }` plus `WIKI_TICKET_MODE` and `LINEAR_TEAM_KEY` from
`.claude/wiki-project.env`.

## Per-Type Framing

- **`decided` / `superseded`** — full actionable template: **Context** (from the decision's
  `## Statement` and `evidence_quote`), **What the User Can Do** (concrete outcome), **Acceptance
  Criteria** (derived from the decision's substance). For `superseded`, note in Context which
  earlier `DEC-NNNN`/ticket this replaces.
- **`unresolved`** — Open Questions framing: what's undecided, what's known so far, what needs to
  be resolved before implementation can start. Not an actionable template — this ticket's purpose
  is to track the open question, not to spec a build.
- **`rejected`** — Why It Was Rejected framing: what was proposed, why it was turned down, and
  (if relevant) what happens instead. Filed so the rejection itself is discoverable later,
  preventing the same idea from being re-proposed without context.

Every section is filled **only from what the meeting evidence actually supports** — an
unsupported section reads `_Not specified in source — needs elaboration before implementation._`
rather than inventing detail to fill it in.

## Steps

1. Determine the framing template from `reconciled_type` (above).
2. Build the ticket body from the decision record's `## Statement`, `evidence_quote`, and
   `reconciliation` fields — never re-summarize from the raw meeting text directly; the decision
   record is the authoritative distillation at this point.
3. **If `WIKI_TICKET_MODE == "draft"`:** do not call Linear. Leave `linear_issue: null` in the
   decision record (already the default from `wiki-writer.md`). Add this ticket's title + body to
   this run's `pending` list for the final report — no local ticket file is written (that would
   duplicate content the decision record already holds).
4. **If `WIKI_TICKET_MODE == "live"`:** call `mcp__claude_ai_Linear__save_issue`, routed into
   `LINEAR_TEAM_KEY`'s **Triage** state specifically (not the team's default workflow state) — a
   human reviews every wiki-sourced ticket before it's actionable. If `LINEAR_TEAM_KEY` isn't set
   yet, ask the user which Linear team this project files into, then write it back to
   `.claude/wiki-project.env` so future runs don't ask again.
5. **Update the decision record and `decisions/index.md`:** set `linear_issue` to the created
   issue's URL (live mode only), and fill in the ticket-link column in `decisions/index.md`'s row
   for this `DEC-NNNN` that `wiki-index-updater.md` left blank.

## Output

`{ dec_id, ticket: { mode: "draft" | "live", url: string | null } }`

## Rules

- **No gate here** — every non-duplicate decision gets a ticket, regardless of type. The framing
  differs by type; whether a ticket gets created does not.
- Always route live-mode tickets into **Triage**, never a team's default/ready state — a human
  reviews every wiki-sourced ticket before it's picked up for work (this is also what
  `linear-implement-trigger` watches for: tickets a human has since moved *out* of Triage).
- Never fabricate acceptance criteria, context, or a rejection rationale beyond what the source
  evidence supports — use the explicit "not specified" language instead.
- Draft mode never touches Linear and never writes a local ticket file — the decision record
  itself, plus this run's summary, are the only records of a draft-mode "would-be" ticket.
