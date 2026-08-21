---
name: wiki-ticket-recorder
description: Record a Linear ticket's current state (description + acceptance criteria + labels) into this project's product wiki as a decision record. The adapter between product-align-loop's per-round ticket loop and the wiki-ingest pipeline's writer/index steps — it never re-implements them. Commits the result to the branch already checked out; never pushes, never opens a PR (create-prs owns that separately). Idempotent — a second run on unchanged ticket content and unchanged outcome produces no new commit.
---

# wiki-ticket-recorder

`wiki-writer.md`/`wiki-index-updater.md` expect a *reconciled meeting item* — this skill's whole
job is producing that shape from a Linear ticket instead of a transcript, then handing off
unmodified. It also reuses `wiki-feature-mapper.md`, `wiki-feature-onboarder.md`,
`wiki-conflict-detector.md`, and `wiki-resolution-handler.md` exactly as `wiki-ingest`'s per-item
pipeline does — none of that reconciliation logic is re-implemented here. What's genuinely new:
turning ticket state into the item's raw fields, the content-hash idempotency gate, and a small
`linear_issue` patch that stands in for `wiki-ticket-creator.md` (see Step 9 — this ticket already
exists, it is never re-created).

Unlike `wiki-ingest`, this does not run on the shared `wiki/init-scaffold` branch. It runs inside
whatever branch is already checked out for this ticket's own work — the wiki record rides along in
that ticket's eventual PR rather than a separate wiki-only changeset. Do not "fix" this to redirect
onto `wiki/init-scaffold`; that branch is for meeting-sourced content, this is ticket-sourced.

## Args

Exactly: a ticket identifier, a Linear team key, and the target repo as `owner/repo`. All three
required, never auto-resolved — same convention as `product-align-loop`'s Args, for the same
reason: the caller already knows which ticket changed and why this run was triggered.

Example: `/wiki-ticket-recorder AI-123, team AI, repo kickdrum/project-flightdeck`

## 1. Resolve `project-id` and guard

Derive `project-id` the same deterministic way `/init-product-wiki` does — from this repo's
`CLAUDE.md` title, kebab-cased. Never ask, never invent a different id; the already-scaffolded
`wiki/{project-id}/` tree depends on this derivation being identical every run.

```bash
find "wiki/${PROJECT_ID}" -maxdepth 2 -name "*.md" 2>/dev/null
```

Nothing found → stop, tell the user to run `/init-product-wiki` first. Read `wiki/SCHEMA.md`
fresh — it is the format contract for every write below, not anything hardcoded here.

Confirm this working tree's `origin` matches the supplied `owner/repo`. Mismatch → stop and report
it rather than silently writing into the wrong clone's wiki tree.

## 2. Fetch the ticket

Get the ticket and its full comment thread, oldest→newest, using **the project's own Linear MCP
server** — the same one `product-align-loop` uses, whose tools are named `mcp__<server>_linear__*`
(in Flight Deck's case `mcp__flightdeck_linear__get_issue` / `..._list_comments`).

**Not the claude.ai Linear connector** (`mcp__claude_ai_Linear__*`). That one authenticates as
whichever human connected it, so everything it touches is attributed to that person rather than
to the agent — which is the entire reason these flows run a separate local server instead. It is
also excluded outright by `--strict-mcp-config`, so in a headless run those tools do not exist and
naming them just fails the round.

Read-only here: this skill never writes to Linear. The upstream align skill owns every comment and
label on the ticket; this one only records what the ticket already says.

Confirm the ticket's team matches the supplied team key and its identifier prefix matches it too —
either mismatching means stop and report, not proceed.

Run `wiki-sanitizer.md`'s rules (strip unsafe markup, redact secret-shaped strings, enforce the
size cap, wrap as `[EVIDENCE]`) over the description and comment bodies before any of them are
quoted into a wiki file below — this ticket text ships into a file that lands in a PR eventually,
exactly the case that skill's redaction step exists for.

## 3. Compute `Ticket-Content-SHA`

Defined language-agnostically, so any implementation (this shell pipeline, a future Python
reimplementation, whatever) produces the same digest from the same ticket: take the description
exactly as the fetch call returned it — `Acceptance Criteria` is one of the standard-structure
sections *inside* that description (per `product-align-loop`'s own structure), not a separate
field Linear exposes, so hashing the description already covers it; there is nothing else to hash
separately — normalize CRLF→LF, strip **all** trailing newlines, encode as UTF-8, then SHA-256 the
bytes and lowercase-hex the digest.

**Do not pass the description through shell interpolation** (a variable, a heredoc, `printf` with
the text as an argument) — ticket markdown routinely contains backticks, `$`, and quotes, and
shell re-expansion of those characters changes the byte sequence being hashed, differently
depending on how each run happens to quote it. That silently breaks the "identical content →
identical hash" guarantee this whole mechanism depends on. Instead, use the `Write` tool to put the
description byte-exact into a temp file, untouched by the shell, then hash the file:

```bash
sed 's/\r$//' "$TMP_DESCRIPTION_FILE" > "$TMP_NORMALIZED"
# $(cat ...) strips only trailing newlines (never internal ones), and a quoted expansion never
# re-parses the captured bytes as shell syntax — safe, unlike interpolating raw markdown directly
# into a command line or an unquoted heredoc.
HASH=$(printf '%s' "$(cat "$TMP_NORMALIZED")" | shasum -a 256 | awk '{print $1}')
```

(`sha256sum` on Linux.) Whatever pipeline is used, verify it against the definition above, not
against this shell snippet — the snippet is one way to hit the spec, not the spec itself.

## 4. Find any prior record for this exact ticket

Anchor on a word boundary — a plain substring match on `${TICKET_ID}` also matches `AI-1234` when
looking for `AI-123` (or `AI-123` when looking for `AI-12`), which would seed conflict-detection
from the wrong ticket's record:

```bash
grep -rlE "linear_issue:.*\b${TICKET_ID}\b" "wiki/${PROJECT_ID}/decisions/DEC-"*.md 2>/dev/null
```

If found, read that `DEC-NNNN` in full — its `type` and `## Statement` are the baseline this run
compares against, deterministically, rather than leaving `wiki-conflict-detector.md` to rediscover
the connection by prose similarity alone.

## 5. Derive `type` from current ticket state

- `aligned` label present → `decided`
- `rejected-codebase-mismatch` label present → `rejected`
- neither present (mid-loop, `open-questions` or nothing yet) → `unresolved`

Raw `type` here is only ever one of these three — `superseded`/`duplicate` are reconciliation
outcomes assigned in Step 8, never derived directly from labels (same discipline
`wiki-decision-classifier.md` documents).

## 6. Idempotency gate

Every commit this skill makes (Step 8's empty duplicate-commit included) carries three trailers:
`Ticket`, `Ticket-Content-SHA`, and `Ticket-Type` (Step 5's label-derived type — not
`reconciled_type`, which can be `superseded`/`duplicate` and would never match a fresh label-derived
value, defeating the gate on every re-invocation after a supersession). Gate on all three together:

```bash
git log --all -F --all-match \
  --grep="Ticket: ${TICKET_ID}" \
  --grep="Ticket-Content-SHA: ${HASH}" \
  --grep="Ticket-Type: ${TYPE}" \
  --format=%H
```

Non-empty output → this exact content, under this exact derived outcome, was already recorded.
Report `unchanged, no commit` and stop. Checking the hash alone would miss a ticket that flips
label (e.g. `open-questions` → `aligned`) with the description already fully folded in from the
prior round — same hash, materially different outcome — so `Ticket-Type` must be part of the same
gate, not compared separately against Step 4's DEC lookup (which exists only to seed
conflict-detection, not to gate this step).

If empty, continue to Step 7.

## 7. Build the raw item

| Field | Source |
|---|---|
| `summary` | One sentence from the ticket's `Summary` section (or title, if round 1 hasn't structured it yet) |
| `evidence_quote` | Real ticket text, quoted verbatim from the sanitized text with the `[EVIDENCE]` wrapper marker itself excluded — never a fabricated utterance, never a URL, never the literal wrapper. `decided` → the most central `Acceptance Criteria` bullet. `rejected` → the bot's rejection comment's core sentence (the one stating what the codebase actually says). `unresolved` → the latest open-question line, or the `Summary` sentence if no bot comment exists yet. |
| `recording_id` | The ticket identifier (e.g. `AI-123`) |
| `transcript_id` | The ticket URL |
| `source_meeting` | Label `"Linear ticket <TICKET_ID>"` — a label, not a file, same reason the schema gives for meeting-sourced items: no local meeting page exists here either |

A ticket has one artifact, not two — `recording_id`/`transcript_id` both point at it, in different
forms (bare id vs. full URL), so either can be grepped for later. This, and quoting real ticket
text into `evidence_quote` instead of provenance text, are this adapter's two deliberate departures
from the literal transcript shape — both are documented here, not left to guesswork.

## 8. Reconcile

Run `wiki-feature-mapper.md` (running `wiki-feature-onboarder.md` if it flags a candidate/alias),
then `wiki-conflict-detector.md` over the full `decisions/` tree — seed it with Step 4's prior
record (if found) as a certain `existed_before`/`contradicts` candidate, not something it has to
rediscover by text similarity. If it sets `needs_resolution: true`, run
`wiki-resolution-handler.md` before continuing.

**On a non-interactive run, these two steps behave differently — do not treat them alike.**
This used to be one rule that stopped for both, and on a fresh project it made the wiki
unbuildable: with an empty `feature-requests/index.md` every ticket is a
`new_feature_candidate`, so every ticket hit a step that could not run, so nothing was ever
recorded — and this path is what is supposed to build the wiki forward, ticket by ticket.

- **`wiki-feature-onboarder.md` — proceed.** See its own "Non-interactive runs" section: a
  `new_feature_candidate` is *additive*, so it creates the feature request marked
  `proposed_by: agent` / `identity_confirmed: false`, with the identity question written into
  the file's `## Open Questions` and repeated in the PR description. The human's review of that
  PR is the decision, and it leaves a record an interactive prompt would not. A
  `possible_alias_of` still never merges — it creates a distinct feature request and flags the
  suspicion. Carry both questions into your own report so the caller can surface them.
- **`wiki-resolution-handler.md` — stop.** Resolving a contradiction rewrites existing content,
  which no marking makes reviewable after the fact. If it is reached with no human able to
  answer: **stop, report the specific unanswered question, and write nothing** — no `DEC-NNNN`,
  no commit, not even the Step 8 duplicate empty-commit. A caller re-invokes this skill once an
  answer is available; a silently-resolved contradiction is worse than a ticket left unrecorded
  for one more round.

**If `reconciled_type` comes back `duplicate`:** this is a real, expected path — most rounds append
a `## Round log` line, which changes the hash without changing anything material, and
`wiki-conflict-detector.md` correctly calls that a duplicate. Per `wiki-writer.md`'s skip
condition, write nothing to `decisions/` or `feature-requests/` — but still run:
```bash
git commit --allow-empty -m "$(printf '%s: no wiki change (duplicate)\n\nTicket: %s\nTicket-Content-SHA: %s\nTicket-Type: %s' "$TICKET_ID" "$TICKET_ID" "$HASH" "$TYPE")"
```
Skipping this empty commit would mean the new hash is never recorded, so the next run's Step 6
gate can never find it and the caller re-invokes this skill forever without ever converging — the
empty commit is what makes `duplicate` a terminal, not a repeating, outcome.

## 9. Write and patch `linear_issue`

For a non-duplicate outcome, run `wiki-writer.md` (writes `DEC-NNNN`, edits the feature request if
`feature` is set) then `wiki-index-updater.md` — **always**, even when `feature` is `null`:
`decisions/index.md` still needs its new row regardless. And when `feature` **is** set, the
`feature-requests/index.md` row is not optional either — a reader of this wiki loads that index
first, then the individual `feature-request.md` files; a feature file updated without its index row
is a real, findable file that the read path never actually reaches. Never treat "no feature
matched" as a reason to skip the whole index-update call — only the `feature-requests/index.md`
half of it is genuinely a no-op in that case, and even then `decisions/index.md` still needs it.

Then apply the one follow-up edit `wiki-ticket-creator.md`'s Step 5 already performs in the normal
pipeline — this is that same edit, not a new exception to the decision record's write-once rule:
set the new `DEC-NNNN`'s `linear_issue` field to this ticket's URL, and fill in the ticket-link
column `wiki-index-updater.md` left blank in `decisions/index.md`'s new row. `wiki-ticket-creator.md`
itself never runs here — there is nothing to create, the ticket already exists; this skill's whole
purpose would be defeated by minting a second one.

## 10. Commit

Stage only the wiki tree — never `git add -A` / `git commit -a` — the checked-out branch may carry
this ticket's actual implementation work in progress, unrelated to this recording:

```bash
git add "wiki/${PROJECT_ID}"
git commit -m "$(printf '%s: record wiki state (%s)\n\nTicket: %s\nTicket-Content-SHA: %s\nTicket-Type: %s' "$TICKET_ID" "$RECONCILED_TYPE" "$TICKET_ID" "$HASH" "$TYPE")"
```

`Ticket-Type` here is Step 5's label-derived type (`decided`/`unresolved`/`rejected`), the same
value used to gate in Step 6 — the commit subject's `(%s)` is `$RECONCILED_TYPE` instead, since
that's the more informative thing for a human skimming `git log` (it can say `superseded`, which
`Ticket-Type` deliberately never does).

**Commit only. Never push, never open or touch a PR** — `create-prs` owns publishing, separately,
whenever the caller decides to. Never create or switch branches; commit onto `HEAD` as found.

## Output

Report to the caller: `unchanged` (Step 6), `duplicate` (Step 8, empty commit made), or the new
`DEC-NNNN` + `reconciled_type` + whether a feature request was touched/created. This is what the
caller compares next round — it does not decide anything about the ticket's Linear labels itself
(this skill never calls `save_issue`; it only reads).

## Rules

- Never write a second file-format writer — every wiki file this produces goes through
  `wiki-writer.md`/`wiki-index-updater.md` exactly as `wiki-ingest` uses them.
- `evidence_quote` holds real, verbatim ticket/comment text — never a fabricated quote, and never
  the ticket URL (that's `transcript_id`'s job). This is a deliberate choice: it keeps the field's
  "grounded in something real" purpose intact even though there is no spoken evidence to quote.
- The Step 6 gate is a conjunction (hash **and** type), never hash alone — see Step 6 for why
  hash-only misses a label-only convergence.
- The hash (Step 3) is computed over the raw description, before Step 2's sanitization — sanitize
  for display/quoting, hash the source.
- `wiki-ticket-creator.md` never runs from this skill — Step 9's `linear_issue` patch replaces it,
  because the ticket already exists.
- This lands on the ticket's own branch, not `wiki/init-scaffold` — do not redirect it there.
