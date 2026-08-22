---
name: pr-review-headless
description: Headless, non-interactive review of a pull request across both backend and frontend changes - full context gathering, rule-based analysis, and inline comment posting, with no human checkpoint.
disable-model-invocation: true
argument-hint: <pr-url-or-number>
allowed-tools:
  - Read
  - Glob
  - Grep
  - Bash
---

# Review Pull Request (Headless)

Full-workflow review across whichever repos/apps the PR touches (backend, frontend, or both), with
context gathering, configurable rules, severity-based analysis, and inline comment posting - **no human
checkpoint**. This is a fork of `pr-review-backend`/`pr-review-frontend` merged into one pass and adapted to
run unattended inside a container with no human to ask: the `AskUserQuestion` checkpoint present in both
interactive originals is removed entirely - findings are posted directly once analysis
completes. Severity vocabulary is `BLOCKER` / `WARNING` / `NOTE` (not the icon-based Blocker/Suggestion/Nit
labels the interactive skills use), matching exactly what `receiving-code-review/SKILL.md` and the
`code-reviewer` agent already expect - so a fix round consuming this review's output needs no translation.

**Why this has a dedicated Correctness/Concurrency/Lifecycle sweep (Section 3) instead of more review rounds:**
a same-PR comparison against a separate adversarial multi-lens reviewer found that both passes caught the same
rule-file-driven bugs, but this skill missed three real re-entrancy/lifecycle bugs in frontend state that no
rule file describes. The gap was in what a single pass *looked for*, not how many rounds ran - round 1 came
back clean (0 blockers) on that PR, which is correct behavior in a loop where findings trigger fix rounds
until the PR is clean: a clean round is *meant* to end the loop, not trigger another one for its own sake,
since a second round exists to re-verify a fix, not to re-look for what the first round missed. Forcing a
second round on a clean PR would not have caught these either, since nothing about it does a fresh sweep. So
the fix lives inside this one round's analysis instead - see the sweep in Section 3.

---

## 1. Input Parsing

PR reference: `$ARGUMENTS`

Parse the PR reference to extract `OWNER` / `REPO` / `PR_NUMBER` from a URL
(`https://github.com/OWNER/REPO/pull/123`). A bare number is not supported in headless mode - the caller
must always pass a full PR URL, since there is no single default repo (a review can run against backend
or frontend changes in the same PR).

If `$ARGUMENTS` is empty or not a parseable PR URL, do not ask - treat this as a hard failure and emit the
escalation JSON (see Section 7) with `reason: "no PR URL provided or unparseable"`.

---

## 2. Context Gathering

Gather all context before analysis.

### 2a. PR Metadata
```bash
gh pr view $PR_NUMBER --repo $OWNER/$REPO --json title,body,headRefName,baseRefName,commits,files,labels,author
```

### 2b. Full Diff
```bash
gh pr diff $PR_NUMBER --repo $OWNER/$REPO
```

### 2c. Ticket Context (if available)
<!-- CUSTOMIZE: Replace ticket ID pattern with your project's pattern, e.g., PROJ-\d+ -->
- Extract ticket ID from PR title, branch name, or body (pattern: `TICKET-\d+`)
- Check for execution artifacts: `Glob: docs/execution/{TICKET_ID}-*/requirements.md`
- Also load `implementation-plan.md` and `execution-state.md` from the same execution directory if present

**Degraded-mode handling (no human to warn, so just proceed and note in the final report):**
- **No ticket ID found** → note it, skip acceptance-criteria checking, proceed with a code-quality-only review.
- **Ticket found but no acceptance criteria** → note it, limit the completeness check to code-level analysis.
- **No execution artifacts found** → note it and proceed normally; execution artifacts are optional context.

### 2d. Load Conventions
Read the following for project conventions:
<!-- CUSTOMIZE: Paths to your repo's CLAUDE.md files -->
- Root `CLAUDE.md`
- `CLAUDE.md` and `CLAUDE.md` (if present)

### 2e. Load Review Rules
Read only whichever of these actually apply to the files changed in this diff (skip the rest entirely -
e.g. skip `frontend-*.md` if the diff touches no frontend files). They define what to check and at what
severity. Where the tool allows it, batch multiple file reads into a single tool call rather than one call
per file, to keep this step's turn cost proportional to how many rule files actually apply, not the total
number that exist:
<!-- CUSTOMIZE: Adjust rule file list to match your project -->
- `.claude/rules/backend-lang.md` — architecture, DTOs, security, code quality (backend changes)
- `.claude/rules/backend-migrations.md` — migration conventions (backend changes)
- `.claude/rules/backend-testing.md` — integration test patterns (backend changes)
- `.claude/rules/frontend-lang.md` — components, test identifiers, path aliases (frontend changes)
- `.claude/rules/frontend-state.md` — state management, API layer, caching (frontend changes)
- `.claude/rules/security.md` — auth, input validation, SQL injection, secrets, XSS (always)
- `.claude/rules/general-quality.md` — error handling, logging, naming, dead code, API contracts (always)
- `.claude/rules/testing-standards.md` — test coverage, unhappy paths, assertions (always)

Each rule section has a `<!-- severity: ... -->` marker (`blocker` / `suggestion` / `nit`). Map to this
skill's vocabulary: `blocker` → **BLOCKER**, `suggestion` → **WARNING**, `nit` → **NOTE**.

---

## 3. Analysis

For each changed file in the diff:

1. **Review the diff hunks directly** (already gathered in 2b) - each hunk already includes surrounding
   context lines, which is normally enough to judge a finding. **Only `Read` the full file** when a specific
   suspected issue genuinely cannot be confirmed from the hunk's own context (e.g. checking whether a helper
   used in the diff is already imported, or whether a pattern elsewhere in the file conflicts with the
   change) - do this selectively, per suspected issue, not as a blanket first step for every changed file.
   This keeps turn cost proportional to the diff's actual size instead of the repo's file sizes.
   **Exception:** for the Correctness/Concurrency/Lifecycle sweep below, always `Read` the full file for any
   changed file with async state, a timer, a subscription, or a multi-step interaction — the bug is typically
   in how two handlers in the *same* file interact (e.g. a submit handler and a dismiss handler touching the
   same state), which an isolated hunk cannot show even when the suspicion is already specific.
2. **Apply all applicable rules** from the loaded rule files
3. **Check acceptance criteria** coverage if a ticket was found — and while doing this, check for a
   **scope-level problem** first (see below), before categorizing anything else
4. **Categorize each finding**:

| Severity | Meaning | Maps from rule severity |
|----------|---------|--------------------------|
| **BLOCKER** | Must fix before merge | `blocker` |
| **WARNING** | Should fix, non-blocking | `suggestion` |
| **NOTE** | Minor style/preference, or a question/praise worth recording | `nit` (or reviewer judgment for questions/praise) |

### Scope-Level Findings (checked before any of the above)

A scope-level finding is different in *kind* from BLOCKER/WARNING/NOTE, not just more severe than
BLOCKER — it means the diff correctly reflects a real attempt to implement the ticket, but the
**ticket itself** is the problem, not the code:

- The acceptance criteria are directly contradictory or infeasible as written (e.g. "AC-1: field X
  must always be set" and "AC-2: field X must never be set" in the same ticket).
- Implementing this correctly requires a decision beyond what a code reviewer should make
  unilaterally (a product/UX call, a data-model choice affecting other tickets, a compliance
  judgment) — and the ticket gives no guidance on which way to go.
- The diff reveals the ticket names or describes the wrong feature/endpoint/flow entirely — not "the
  implementation has a bug," but "this ticket and this diff are solving different problems."

**Not** scope-level, no matter how severe: a missing edge case, a real bug, a security hole, a
missing test, an architecture violation — however bad, those are still BLOCKER. Scope-level is
specifically "the ticket is broken," never "the code is broken."

**If found, it takes priority over everything else in the same round.** Set `scope_findings` (count)
and `scope_reason` (a combined explanation) in the trailing JSON (Section 6) — continuing to patch
code under a contradictory or infeasible spec compounds the problem rather than resolving it. Still
post whatever real BLOCKER/WARNING/NOTE findings exist too (transparency), but make the scope
concern clearly visible as its own statement in the review body, separate from the inline findings.

### Correctness / Concurrency / Lifecycle Sweep

This is **not** a rule-file item — it's a fixed dedicated pass because rule-file matching cannot catch it. Rules
match patterns in isolated hunks; the bugs here only exist in how two pieces of code interact over time, which
requires actually tracing sequences, not pattern-matching a diff.

For every changed file that has async state, a timer, a subscription, or a multi-step user interaction (a
form, a modal, a submit handler, an effect), trace through:

- **Re-entry**: if the user (or a retried/duplicated request) triggers this action again before the current
  one resolves, what happens? Can two in-flight calls race, and does the second one silently clobber state the
  first one set (a flag, an error banner, a timestamp, a DB row)?
- **Stale references after resolution**: does a `.then()`/`finally()`/effect-cleanup block assume the state it's
  about to touch (an id, a modal's open state, an error field) still belongs to the same interaction that
  started it, or could the user have moved on to a different item by the time it runs?
- **Guard-vs-write gaps on writes**: if a check (ownership, status, existence) is read once and then used to
  justify a write later, does the write itself re-assert that same condition (e.g. a `WHERE status = 'x'` on
  the UPDATE), or can the state have changed between the read and the write?
- **Disabled-in-one-place-only guards**: if a control is disabled to prevent a double action, is it disabled
  everywhere that action is reachable (mouse and keyboard, every row/instance, not just the one the user most
  recently interacted with)?

Flag every genuine instance as a finding with the concrete trigger sequence (not "under high concurrency" —
the actual steps: "open X, do Y while Z is pending, then observe W"). **Require a concrete fix in the finding
itself** (the specific guard/clause/state-clear to add), not "consider adding X or at minimum a comment noting
the gap" — a suggested fix that a fix round could skip by adding a comment instead is not a useful finding.

**Severity — this is not a rule file, so assign it by judgment, using the same bar as everywhere else in this
skill:**
- **BLOCKER** — the race silently corrupts or loses data, breaks a stated acceptance criterion or documented
  guarantee, or has any security implication. A write that overwrites another write with no trace of the lost
  one, or a check that a race lets an attacker bypass, is a blocker even though no rule file names it — "no
  rule matched it" is not grounds for downgrading a real correctness bug. Do not soften this to WARNING because
  it came from this sweep instead of a rule file.
- **WARNING** — a real race or stale-reference bug, but one that degrades UX, is hard to trigger, or affects a
  non-critical path rather than losing data or breaking a stated guarantee.
- **NOTE** — a theoretical gap with no realistic trigger path, or a missing acknowledgment/comment on an
  already-known, already-accepted tradeoff.

This mirrors the stricter definition of Blocker used by adversarial multi-lens review ("code that breaks
behavior, loses data, or is a security hole") specifically because a same-PR comparison against such a review
found this exact category of bug, and its stricter severity bar is part of what made it more actionable — not
just that it looked harder.

### Completeness Check

After rule-based analysis, perform a dedicated completeness sweep:

- **Acceptance criteria coverage** — if ticket context with acceptance criteria is available, produce a
  table mapping each criterion to Addressed / Partial / Missing, with a brief note each. If unavailable,
  skip the table and note why.
- **Missing tests** — flag new code paths (service methods, controllers, components, hooks, utilities)
  lacking corresponding test coverage.
- **Missing migrations/config** — flag new entity fields/tables/relationships without a migration; new env
  vars or config properties used without being defined.
- **Cross-repo notes** — if the PR changes API response/request shapes, note that the other side (frontend
  consumers, or backend if this is a frontend PR) may need corresponding updates.

### Quick-Reference Checklist

Backend files changed:
- [ ] Follows established layered architecture pattern
- [ ] Authorization on new endpoints
- [ ] DTOs used (entities never returned from controllers)
- [ ] Migrations follow naming conventions, no modification of existing migrations
- [ ] Integration tests cover new endpoints with real database
- [ ] No hardcoded secrets, no SQL injection, input validation present
- [ ] Null safety handled (no unchecked access)

Frontend files changed:
- [ ] Functional components with hooks, explicit prop types
- [ ] All interactive elements have test identifier attributes
- [ ] No unjustified `any` types, proper null/undefined handling
- [ ] Uses project path aliases for shared imports
- [ ] Loading, error, and empty states handled for data-fetching components
- [ ] State management follows project patterns

Always:
- [ ] No N+1 query patterns
- [ ] Formatting applied, commit messages follow project format
- [ ] Re-entrant actions (re-submit, double-click, retried request) can't race each other into a bad state
- [ ] Async completion handlers (`.then`/`finally`/effect cleanup) don't assume the interaction that started them is still the current one
- [ ] Guarded writes re-assert their guard condition at write time, not just at an earlier read

---

## 4. Post Inline Comments

No user checkpoint - proceed directly from analysis to posting. Post **all** findings in a **single**
`gh api` call (the endpoint accepts an array of comments in one review) rather than one call per finding -
repeat the `comments[][...]` field group once per finding within that same invocation:

```bash
gh api repos/{OWNER}/{REPO}/pulls/{PR_NUMBER}/reviews \
  --method POST \
  --field body="<summary>" \
  --field event="<APPROVE|COMMENT|REQUEST_CHANGES>" \
  --field 'comments[][path]=<file-1>' \
  --field 'comments[][position]=<diff-position-1>' \
  --field 'comments[][body]=<severity-tag> <message-1>' \
  --field 'comments[][path]=<file-2>' \
  --field 'comments[][position]=<diff-position-2>' \
  --field 'comments[][body]=<severity-tag> <message-2>'
```

> **Tip:** `position` is the 1-indexed line offset within the diff hunk (from the `@@` line). If position
> calculation proves unreliable, use `subject_type: "line"`, `line`, and `side: "RIGHT"` instead.

### Error Handling (no human to inform - log and continue toward the escalation JSON)

- **Line not in diff** → do not post as inline; fold into the review body summary instead.
- **Auth error (401/403)** → this is a hard failure. Emit the escalation JSON (Section 7) with
  `reason: "gh auth error - <status> on <method> <endpoint>"`, e.g.
  `"gh auth error - 401 on POST /repos/{owner}/{repo}/pulls/{n}/reviews"`.
- **PR closed or merged** → emit the escalation JSON with `reason: "PR is closed/merged, cannot review"`.
- **General API failure** → retry once; if it fails again, emit the escalation JSON with the status and
  endpoint in the same form.

> **Never put raw command output in `reason`.** The status code and the endpoint are what a person needs to
> act on; everything else in a failed `gh` invocation is a liability. This run holds a repository token and a
> model credential in its environment, and a failing `gh` call is exactly where they surface — in the command
> line it echoes, in a response header, in a verbose error body. `reason` is not a private log: it is
> returned to the orchestrator, stored, and may be shown or posted somewhere public.
>
> So `reason` carries **only** what you have composed yourself. Never paste in a command line, a response
> body or headers, an environment variable, a stack trace, or anything read from `env`. If you cannot
> describe a failure without quoting output, describe it in your own words and give the status and endpoint
> alone.

### Determine review action
- Any **BLOCKER** → `REQUEST_CHANGES`
- Only **WARNING** or lower → `COMMENT`
- Only nits/praise, nothing else → `APPROVE`

### Comment format (terse, one-line per finding, rule ID for traceability)
```
BLOCKER [BE-03] Missing authorization on new endpoint
WARNING [GEN-08] Potential NPE — Optional.get() without isPresent check
NOTE [GEN-03] Consider renaming `proc` to `processor` for clarity
```
Findings from the Correctness/Concurrency/Lifecycle sweep (not tied to a rule file) use `[CONCURRENCY]` in
place of a rule ID, e.g. `WARNING [CONCURRENCY] Two concurrent cancel requests both pass the status guard...`

---

## 5. Update Execution State (if present)

If `docs/execution/{TICKET_ID}-*/execution-state.md` exists (this run is reviewing its own implementer's PR),
append a log entry noting the review round's outcome (action, blocker/warning/note counts) - do not
overwrite the file, only append to its `## Log` table.

---

## 6. Report — trailing structured JSON (required, replaces the interactive "Report" step)

Output EXACTLY ONE JSON object on the last line of your final message, matching this shape and nothing else
on that line:

```json
{"status":"reviewed","action":"REQUEST_CHANGES","blockers":2,"warnings":3,"notes":1,"scope_findings":0,"scope_reason":null,"review_url":"https://github.com/OWNER/REPO/pull/123#pullrequestreview-..."}
```

`action` is exactly one of `"REQUEST_CHANGES"`, `"COMMENT"`, `"APPROVE"`. `review_url` is the URL of the
review just posted (from the `gh api` response's `html_url` field). `scope_findings`/`scope_reason` are
`0`/`null` unless the Scope-Level Findings check above found something — see that section for what to
put in `scope_reason` when it isn't.

## 7. Escalation JSON (only on a hard failure per Section 4's error handling)

```json
{"status":"escalated","reason":"..."}
```

`reason` is a sentence you wrote, never text you captured. It must not contain a command line, a response
body or headers, an environment variable, a stack trace, or anything read from `env` — see the rule in
Section 4's Error Handling for why. A status code and an endpoint are enough to act on.
