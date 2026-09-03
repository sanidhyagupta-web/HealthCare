---
name: product-align-loop
description: Run one round of the align/refinement loop on a Linear ticket — classify and format-check, check ticket claims against the real codebase, extract claims, check for ambiguity, run a one-time skeptic pass, then post follow-up questions, refine the ticket, mark it aligned, or reject it as a codebase mismatch. One invocation is one round; the caller decides whether another follows.
---

# product-align-loop

Runs the Product Loop's "AI Product Align" step directly against real Linear via the Linear MCP tools — no Temporal, no external database. The ticket's own comment thread is the only *conversation* state that matters; the actual codebase (read fresh each run from the clone this round runs in, see "Resolving the codebase and team" below) is the only source of truth about what's actually built. This procedure must be followed the same way every time, whether invoked on demand or from the webhook-triggered flow, since each invocation starts with no memory of prior runs.

The four Linear tools available here (`mcp__flightdeck_linear__*`) post as this app's own identity, never as a human — that's *why* they're a separate local server rather than the usual claude.ai Linear connector (which posts as whoever authorized it). Nothing in this procedure needs to say who's asking; every comment this skill posts already shows up in Linear as the agent asking, by construction, and any human reply in the thread is a real human replying in their own Linear session — never simulated by this skill.

## Resolving the codebase and team

**Adapted for the flightdeck server's webhook-triggered path**: the current
working directory is a fresh clone of the target repo, checked out for this
round. Whether you can *read* it depends on which boundary the round is
running on, and the caller decides that — not this text. Check what you have
actually been granted rather than assuming either way; the "Codebase reality
source" bullet below covers both cases. Team and repo are **always supplied
explicitly by the caller** (see Args) — never auto-resolved by calling a
team-listing tool or by reading a root `CLAUDE.md` project name (this
invocation isn't even given a team-listing tool — only the four Linear tools
named below), and never inferred from the clone's own git remote.

- **Codebase reality source.** The clone at the current working directory, read fresh every round with `Read`/`Grep`/`Glob` when those tools are granted — never guessed from memory, and never re-derived from a prior round, since the clone can differ between runs. Start from `README.md` at the repo root for stated scope and capabilities, then use `Grep`/`Glob` to check any *specific* claim the ticket makes against the actual source — a module the ticket assumes exists, an endpoint it says already works, a table it expects. Reading the code is stronger evidence than the README's description of it, so prefer it wherever a claim is concrete enough to look up.

  **Use only `Read`, `Grep`, and `Glob`.** `Bash` is not granted on this path, so `gh`, `git`, `curl`, `cat`, and shell pipelines are all unavailable — as is `WebFetch`. Do not reach for the GitHub API to fetch files that are already on disk in front of you, and do not ask for approval to run a command: this is a non-interactive run with nobody to grant it, so an approval request ends the round having done nothing.

  Paths are relative to the clone root (`README.md`, not `repos/<owner>/<repo>/contents/README.md`). Stay inside the clone; there is nothing above it worth reading.

  If `README.md` is genuinely absent, say so explicitly in the round's output and continue check 2 from the source tree alone — that is a thin-evidence round, not a failure. Only a *tool* failure (a granted tool erroring, or the working directory not being a repo clone at all) is cause to report the exact failure and stop processing the ticket rather than guessing codebase content.

  **If you have no file tools at all**, this boundary cannot perform check 2, and that is a fact about the boundary rather than something to work around. Say so plainly in the round's output — name check 2 and say it had no available method — and carry on with the checks you *can* run from the ticket's own text and its comment thread. Do not substitute a remote fetch, do not infer codebase state from the ticket's own claims (that is precisely what check 2 exists to test), and do not request approval for a tool you were not granted: nobody is there to grant it, and the request ends the round having done nothing. A round that reports check 2 as unavailable is honest and useful; one that quietly skips it, or that reports the ticket's own assertions back as confirmation, is neither.
- **Linear team.** Supplied explicitly by the caller as a team key — never call `list_teams` or infer it from ticket content.

**Bot signature:** every comment this skill posts must start with the literal line `**product-align-bot**` on its own line, followed by a blank line — this is how later runs recognize "my own prior comments" when re-reading the thread.
**Round cap:** not this skill's to enforce — the caller owns stopping (see step 4)
**Labels used:** `open-questions` (applied whenever a not-converged round posts new questions, removed the moment the ticket reaches any terminal outcome below), `aligned` (converged), `rejected-codebase-mismatch` (rejected — see step 8). `alignment-escalated` also exists but **the caller applies it**, on its own cap or reply timeout — never this skill.

**Report what you did.** End the run by stating, on its own line, exactly one of
`ACTION: questions` · `ACTION: refined` · `ACTION: aligned` · `ACTION: rejected`. The caller reads
this to decide whether anything downstream needs to run — a round that only posted questions has
changed nothing worth recording elsewhere. It is a report, not a decision: the caller verifies it
against the ticket itself and does not take it on trust.

## Args

Called with exactly: a ticket identifier, a Linear team key, and the target repo as `owner/repo` (optionally a branch, default `main`). All three are required — this skill never auto-resolves any of them from `list_teams` or a local `CLAUDE.md`.

Example invocation: `/product-align-loop SAI-3, team SAI, repo Sairam-Kickdrum/KDU-2026-Backend`

- **A ticket identifier + team + repo** → process only that ticket, regardless of its current labels (the caller already knows exactly which ticket changed and why this run was triggered).
- **Team + repo, no ticket identifier** → process every open ticket in that team (skip any already carrying `aligned`, `alignment-escalated`, or `rejected-codebase-mismatch`) — for a bulk/scheduled sweep, not the webhook-triggered path.

## Ownership of description content

- **Original human content** — whatever existed in the description *before this skill's round 1 ever ran on this ticket*, **excluding any heading that already matches a standard-structure section name below** (matched case- and punctuation-insensitively — e.g. a pre-existing `## Summary`, `## Acceptance Criteria`, or `## Scope Boundaries`). Permanently frozen — never edit, remove, or reorder it, on any round. Content under a matching heading is not "original" under this rule; it is that section's own earliest draft (see below), and round 1 folds it in rather than freezing it as a separate block.
- **Standard-structure sections** — `Summary`, `Context — Where This Lives`, `User Flow`, `Error Paths`, `Acceptance Criteria`, `Existing System Behavior`, `Scope Boundaries`, `Reference Documents`, and `Round log`. Owned by this skill from round 1 onward. If the description already has a heading matching one of these names before round 1 ever runs, treat its existing content as this section's own earliest draft — fold it in and rewrite it in place as the one canonical copy, never freeze it separately and never create a second heading of the same name. Where no matching heading exists yet, round 1 creates the section fresh. Every later round freely rewrites these sections in place. A section may never keep saying "Missing" once a reply has resolved it — write the real answer where it belongs, not into a single catch-all summary. The `Work-Type:` line at the top of `Summary` is set once, at round 1 (Check 1), and carried forward unchanged on every later round — never re-derived, and never dropped when `Summary`'s prose gets rewritten in place.
- **Recovering an already-duplicated ticket.** If a ticket's description already has two headings sharing a standard-structure section name (e.g. two `## Summary` sections) — a leftover from before this rule existed, or from any other cause — the next round that touches this ticket collapses them into one: compare both copies against the current checks, keep whichever is more complete and accurate, fold in anything true and non-redundant from the other, and delete the redundant duplicate heading entirely. Note the collapse in `## Round log` (e.g. "Collapsed a duplicate Summary/Acceptance Criteria/Scope Boundaries left over from an earlier round"). This is the one exception to "never edit, remove, or reorder" original content — it applies only to a duplicate of a standard-structure section name, never to genuinely distinct original content (e.g. a `## Repo` pointer, which stays frozen as-is).

## Type slot table (used in step 6)

| Slot | Bug | Feature | Tech-Debt |
|---|---|---|---|
| Current behavior | Required | Optional | Required |
| Expected behavior | Required | N/A | Required (target state) |
| Repro steps | Required | N/A | N/A |
| Severity/impact | Required | Optional | Required |
| User flow (new) | N/A | Required | N/A |
| Migration/rollback plan | N/A | Optional | Required |
| Non-functional AC | Optional | Optional | Required |
| Acceptance criteria | Required | Required | Required |
| Scope boundaries | Required | Required | Required |

## The five checks

| # | Check | Runs | Grounded in |
|---|---|---|---|
| 1 | Classify + format-check | Round 1 only | Ticket text + type slot table |
| 2 | Codebase reality check | **Every round** | The codebase (see "Resolving the codebase and team") |
| 3 | Claim extraction | Every round | Ticket text |
| 4 | Ambiguity check | Every round | Extracted claims |
| 5 | Skeptic pass | Round 1 only | Ticket text + type slot table |

## How each check runs

Every check below is a distinct piece of judgment with its own method — none of them are "just think about it and decide." Checks 1 and 5 run once, in round 1; checks 2, 3, and 4 run every round, per the "Runs" column above.

**Check 1 — Classify + format-check (round 1 only).** Determine the work type (bug/feature/tech-debt) from the ticket's own title and description. Write the classification itself into the `Summary` section as its first line, in the form `Work-Type: Bug`/`Work-Type: Feature`/`Work-Type: Tech-Debt` (exactly one, matching the type just determined), followed by a blank line and then the actual summary prose. Compare its current structure against the type slot table's required/optional slots for that type. Rewrite the description into the standard-structure sections (`Summary`, `Context — Where This Lives`, `User Flow`, `Error Paths`, `Acceptance Criteria`, `Existing System Behavior`, `Scope Boundaries`, `Reference Documents`), preserving the original human content untouched above/before these new sections (see "Ownership of description content"). For any section with nothing to say yet, write an explicit `*Missing — ...*` placeholder describing exactly what's absent — never invent content to fill a gap.

**Check 2 — Codebase reality check (every round).** Runs right after classification, before claim extraction, on *every* round — not just round 1, since a human's reply can introduce a new false assumption just as easily as the original ticket text can. Re-read the codebase fresh from the clone (per "Resolving the codebase and team"), then compare it against: the ticket's `Existing System Behavior` section (once it exists), anything the ticket's title/description/replies assert about what currently exists or already works, and any module the ticket assumes is available. Where a claim names something concrete, `Grep`/`Glob` for it rather than settling for what the README implies. Two distinct outcomes feed into step 8:
- **Mismatch found** — the ticket asserts something the codebase contradicts (a described module doesn't exist at all, or a built module's documented behavior differs from what the ticket claims) → this is what makes step 8 choose **Rejected**.
- **Honest dependency on missing/partial work** — the ticket asks to *build* or *extend* something the codebase says isn't there yet, without claiming it already exists → not a mismatch. Feed this into the normal claim/ambiguity/question flow as a scope question instead (e.g. "this depends on checkout, which doesn't exist yet — should this ticket include building it, or block on a separate ticket?").

**Check 3 — Claim extraction (every round, scoped after round 1).** Rewrite the ticket's rule-bearing sentences as a numbered list of atomic GIVEN/WHEN/THEN statements — split any sentence that bundles more than one condition, merge any run of sentences that together describe only one rule. Ground-truth against any existing `Acceptance Criteria` content first (those are already claims by construction), then extract remaining claims from the rest of the ticket. In round 1 this runs over the whole ticket; from round 2 on, per the step-6 mapping, it runs only over the claims tied to the questions the reply just answered — never re-derive the whole ticket from scratch on a later round.

**Check 4 — Ambiguity check (every round, scoped after round 1).** For each claim from check 3, write two independent, plausible interpretations of it *before* comparing them — this must be two explicit, separate writings, not a single "is this ambiguous?" self-report (self-report alone is unreliable — you'll miss ambiguity you'd catch by actually writing out both readings). If the two interpretations produce the same practical outcome → discard, not a gap. If they diverge and the divergence is material (would produce different behavior, different code, or a different test) → keep it as an open item. If the divergence is purely cosmetic (wording only, same outcome either way) → discard it.

**Check 5 — Skeptic pass (round 1 only).** One dedicated check, run exactly once: "name at least one realistic scenario that this ticket's required slots (per the type table) imply but the ticket's text never addresses." Force at least one finding — do not accept "looks complete" as an answer; if nothing comes to mind immediately, work through each required slot for the ticket's type and ask what a required slot with actual content would need to say that this ticket doesn't. Run each finding through the same material-vs-cosmetic filter as check 4 before keeping it.

## Procedure — for the ticket in scope

1. Fetch the ticket (`mcp__flightdeck_linear__get_issue`) and its full comment thread (`mcp__flightdeck_linear__list_comments`), ordered oldest→newest.
2. If a specific ticket identifier was supplied (the normal case from the webhook-triggered path), process it regardless of its current labels. If instead this run was given only team + repo (bulk mode) and the ticket already has the `aligned`, `alignment-escalated`, or `rejected-codebase-mismatch` label → skip it entirely.
3. Find every comment whose body starts with the bot signature **and** contains "Open questions" — these are this skill's own prior question rounds (this deliberately excludes any escalation/rejection comment). **Round number = count of these.** Zero found = this is round 1, about to happen.
4. **Do not decide whether the loop should stop.** The caller owns the round cap and the
   wait-for-reply — it invokes this skill once per round and escalates on its own cap, so a
   second cap here can only disagree with it. Never post an "escalating after N rounds" comment
   and never apply `alignment-escalated` yourself. The round number from step 3 is still needed
   below, for check scoping and question numbering — that is all it is for now.
5. Find the single most recent bot question-comment (if any), and check whether a human comment
   exists *after* it. This is for the fold-in mapping in step 6, not a decision about whether to
   run: the caller only invokes a round when there is something to act on.
   - **No bot question-comment yet at all** (round 1) → skip to step 6.
   - **Bot question-comment exists, human reply exists after it** → continue to step 6a (mapping) before anything else.
   - **Bot question-comment exists, no human reply after it** → unusual, since the caller waits for
     one. Do not stop and do not re-ask the same questions: re-run the checks against the ticket as
     it now stands, and post only genuinely new items (a human may have edited the description
     rather than replying in the thread).

6. **Round 2+ only — explicit fold-in mapping, before re-running any check.** Read the bot's last numbered open questions and the human's reply in full, then:
   1. State plainly, in your own working notes for this run, which question numbers the reply addresses and which remain open (e.g. "reply addresses Q2 and Q3; Q4 remains open").
   2. Only claims tied to the questions just answered get re-extracted/rechecked in checks 3–4 below — do not re-derive the whole ticket from scratch.
   3. Never re-ask a question this mapping shows was already answered, even partially — if a reply only partially answers a question, ask a narrower follow-up under a *new* number instead of repeating the old one verbatim.

7. **Run the checks for this round**, per their methods in "How each check runs" above:
   - **Round 1:** checks 1, 2, 3, 4, 5, in that order.
   - **Round 2+:** checks 2, 3, 4 only, in that order, scoped per the step-6 mapping. Checks 1 and 5 do not run again, however many rounds the caller allows.

8. **Decide the outcome.** In every branch below that calls `mcp__flightdeck_linear__save_issue` to change a label: **its `labels` field replaces the issue's entire label set — it does not add one label to the existing set.** Always pass the *full* desired list (the labels already on the issue, from step 1's `get_issue` call, with the one change applied), never a single-element array, or every other label on the ticket (priority tags, human-applied categorization) is silently wiped.
   - **Rejected** — check 2 found a genuine mismatch (not an honest missing-module dependency) → post one bot-signed comment stating exactly what the codebase says vs. what the ticket assumed, and nothing else (no questions). Apply `rejected-codebase-mismatch` via `save_issue` (existing labels, minus `open-questions` if present, plus this one). Do not rewrite the description's standard-structure sections beyond noting the rejection reason in `Round log`. Stop — no further rounds, ever, for this ticket.
   - **Converged** — no rejection, zero material ambiguities from check 4, zero unresolved skeptic findings from check 5 (if round 1), and every slot required by the type table has at least one claim → fold everything into the standard-structure sections (per "Ownership of description content"), apply `aligned` via `save_issue` (existing labels, minus `open-questions` if present, plus `aligned`). Do not post another comment. Done.
   - **Not converged** — no rejection, but gaps remain → fold in whatever was resolved this round into the real sections (never leave a resolved section saying `Missing`; note any still-open point inline, tagged with the question number that covers it), append one line to `## Round log` summarizing what happened, then post the next numbered questions:
     - **Cap at 5 questions per round.** If more than 5 material items remain after this round's checks, keep only the top 5 by priority order (skeptic findings and honest-dependency scope questions from check 2 first, then ambiguity items from check 4, then narrower follow-ups from step 6's partial-answer mapping) and note in `## Round log` how many additional items exist and were deferred — they're re-evaluated on the next round's checks rather than lost.
     - First round ever → start at 1; prioritize empty required slots, skeptic findings, and any "honest dependency" scope questions from check 2.
     - Follow-up round → continue numbering from one past the highest number used in the bot's last question comment — never reuse or reset numbers.
     - Post via `mcp__flightdeck_linear__save_comment`: the bot signature line, then "Open questions — please reply referencing the numbers below:", a blank line, then the numbered list (only what's still needed).
     - Apply `open-questions` via `save_issue` (existing labels + this one, if not already present — on round 1 it never is; on round 2/3 it's already there from the prior round and this is a no-op).

## Notes

- Never create or delete tickets, never touch board state/columns, never post to any team other than the one supplied by the caller.
- If a Linear MCP call fails, or a granted file tool errors against the clone, report the exact failure and stop processing this ticket rather than guessing. Never ask for approval to run an ungranted tool — nobody is there to grant it, and the round ends having done nothing.
- Checks 1 and 5 run exactly once per ticket, in round 1 only. Check 2 runs every round without exception — never skip it just because round 1 already found no mismatch, since a later reply can introduce a new one.