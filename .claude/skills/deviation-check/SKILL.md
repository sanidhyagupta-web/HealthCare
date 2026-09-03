---
name: deviation-check
description: Decide whether a PR's delivered diff satisfies its ticket's accepted acceptance criteria — deviation gate for closeout. Decides only; writes nothing, commits nothing, never touches Linear or the PR. Reports a verdict (none/deviation/indeterminate) with a per-criterion status. Report "indeterminate" rather than guessing whenever confidence is genuinely low — an indeterminate verdict is treated identically to a deviation by the caller, so guessing wrong is worse than saying so.
disable-model-invocation: true
allowed-tools:
  - Read
  - Glob
  - Grep
---

# deviation-check

Runs after `closeout-feat-recorder` has already recorded delivered reality into the code-wiki —
this skill's own output changes nothing about that record. It exists to answer one question:
**does the delivered diff actually satisfy the ticket's accepted acceptance criteria?**

**You have no write access, deliberately.** No `Bash`, no `Write`, no `Edit` — a judge that could
also act would blur "this doesn't meet the bar" with "let me fix it," and the acceptance criterion
this ticket ships is that a deviation escalates to a human rather than getting silently patched
over by the same run that found it.

**Implementation-detail differences are not deviations.** A criterion met a different way than the
ticket's author imagined is still met — judge behavior against the criterion's own wording, not
against an imagined implementation. Only judge scope/behavior actually described by the criteria;
do not invent additional bars the ticket never stated.

## Args

A ticket identifier, the path to the delivered diff, and the path to its acceptance criteria (a
JSON array of strings, in order). Both files already exist — read them, do not attempt to
reconstruct either from `git` yourself (you have no `Bash`).

## 1. Read both inputs

Read the delivered diff and the acceptance criteria file in full. If either path does not exist or
is empty, that is not something to guess past — report `verdict: "indeterminate"` for every
criterion (`status: "contradicted"` is never appropriate here; use `"unmet"` and say why in
`summary`) rather than inventing a judgment from nothing.

## 2. Judge each criterion independently

For every criterion, in the given order, decide:

- `"met"` — the delivered diff satisfies this criterion, on its own wording.
- `"unmet"` — nothing in the diff addresses this criterion, or what's there falls short of it.
- `"contradicted"` — the diff actively does the opposite of what this criterion requires.

Judge from the diff alone plus whatever the diff's own surrounding context makes visible (`Read`/
`Glob`/`Grep` the checked-out tree as needed) — never from assumptions about code the diff does not
touch.

**When genuinely unsure about one criterion, that criterion is `"unmet"`, and the overall verdict
must be `"indeterminate"`, never `"none"`.** Confidently reporting `"met"` for a criterion you
could not actually verify is the exact failure mode this skill exists to prevent — the caller
treats your `"none"` as license to proceed straight to human review.

## 3. Report the verdict

End your final message with **exactly one** JSON object, with nothing else on that line:

```json
{"verdict":"none","per_item":[{"criterion":"...","status":"met"}],"summary":"..."}
```

- `per_item` must have **exactly one entry per acceptance criterion given to you, in the same
  order** — the caller rejects a short or padded list rather than guessing which criterion a
  missing entry was for.
- `verdict` is `"none"` only when every entry is `"met"`. Any `"unmet"`/`"contradicted"` entry
  means `"deviation"`. Report `"indeterminate"` whenever you could not form a confident judgment at
  all (see Step 1/Step 2) — never fall back to `"none"` for want of certainty.
- `summary` is one line, naming the actual reason for the verdict — not "some requirements not
  met." A human reads this in a PR comment naming the unmet criteria explicitly; `summary` is the
  sentence introducing that list.
