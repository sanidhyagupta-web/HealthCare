# Product Wiki Schema & Conventions

This file defines conventions for every file under `wiki/{project-id}/`. Follow them precisely —
without a single enforced format, drift creeps in: inconsistent frontmatter, inconsistent
linking, inconsistent layout from one write to the next.

This is a **product wiki**: everything under `feature-requests/` is a *feature request* — a
capability proposed, being defined, or being changed — not a *feature* in the sense of code that
already exists. A separate codebase wiki (out of scope here) is where already-built system
architecture belongs; product-wiki pages never link into it.

In production this is **one repo, one project, one wiki** — `wiki/{project-id}/` is one full
instance of everything below.

---

## Current-State vs. Immutable-Ledger Discipline

Two kinds of file live here, with opposite update rules.

**Immutable ledger** (`decisions/DEC-*.md`): write-once. Never edited except adding a single
`superseded_by` field to an old decision when a later one explicitly supersedes it.

**Current-state** (most of `feature-requests/{id}/feature-request.md`: Current State, Key Facts,
Requirements, Business Rules, Open Questions, Risks, Relationships): represents *today's truth*,
not a history log. When a decision changes what's true, replace or trim the stale line and link
the `DEC-*` that changed it — never just append forever.

**Thin indexes** (`feature-request.md`'s `## Decisions`/`## Evidence` sections,
`feature-requests/index.md`, `decisions/index.md`): links and one-line pointers only. Never
restate a decision's `## Statement` in one of these — link to it instead.

---

## Slug & ID Formats

- Decision IDs: `DEC-NNNN`, sequential, zero-padded, per-project. Scan `decisions/DEC-*.md` for
  the current max and increment — never reuse or renumber once assigned. Filename is
  `DEC-NNNN_<kebab-case-slug-from-title>.md`; the `DEC-NNNN` prefix is what's authoritative for
  cross-references, the slug is a cosmetic, one-time label.
- Feature-request IDs: kebab-case, short, stable (e.g. `billing-export`). Treat renaming one as a
  breaking change to every link pointing at `feature-requests/{id}/`.

---

## `wiki/{project-id}/index.md` — project landing page

A short entry point that links out, not a raw content dump:

```markdown
# Wiki — <Project Name>

Last updated: <date>

- [Feature Requests](feature-requests/index.md) — what this project does, organized by capability
- [Decisions](decisions/index.md) — the full project-wide decision ledger
```

---

## `feature-requests/` — feature-request tree

One directory per feature request, created the first time a decision is confidently mapped to
it. Everything about a feature request lives in one file, `feature-request.md` — not split
across separate files.

### `feature-requests/index.md` — feature-request catalog

The first place to look to see "what does this project do" — one row per known feature request,
mapping to its `feature-requests/{feature-id}/feature-request.md`:

```markdown
# Feature Requests — <Project Name>

Last updated: <date>

| Feature Request | Summary | Status | Open Questions | Last Touched |
|---|---|---|---|---|
| [billing-export](billing-export/feature-request.md) | Billing export job and its trigger | active | 0 | <date> |
```

### `feature-requests/{feature-id}/feature-request.md`

```yaml
---
title: "Billing Export"
slug: billing-export
owners:
  - <owner name>
status: active   # active | deprecated
last_updated: <date>
---

## Current State
<Plain-language description of how this feature request works TODAY. Rewrite/trim as decisions
change it — not a running log of everything ever said about it.>

## Key Facts
- <Fact that holds today, linked to the DEC-NNNN that established it>

## Requirements
- <Requirement that holds today, linked to the DEC-NNNN that established it>

## Business Rules
- <Rule that holds today, linked to the DEC-NNNN that established it>

## Decisions
| Date | Title | Type | Ticket |
|---|---|---|---|
| <date> | [Title](../../decisions/DEC-NNNN_<slug>.md) | decided | [Linear](<url>) |

## Evidence
- [DEC-NNNN](../../decisions/DEC-NNNN_<slug>.md)

Links only, to `decisions/DEC-*.md` — never a copied excerpt of the transcript. The verbatim
quote already lives on the Decision Record's `evidence_quote` field; there is no separate
meeting page to link to instead (see "No Local Meeting Archive" below).

## Open Questions
- <Unresolved question>

**Resolved:**
- ~~<Former question>~~ → resolved by [DEC-NNNN](../../decisions/DEC-NNNN_<slug>.md)

## Risks / Rejected Approaches
- <Rejected approach or known risk, linked to the DEC-* that recorded it>

## Relationships
**Depends On:** <feature-id> — <one-line reason, linked to the DEC that established it>
**Related:** <feature-id> — <one-line reason>
```

Every section heading stays present even when empty — write "Nothing recorded yet." rather than
omitting it, so the next write has an obvious place to land. `## Decisions` and `## Evidence` are
thin indexes (links only); every other section is current-state.

---

## `decisions/` — canonical, project-wide decision ledger

The durable memory that answers "was this already decided / rejected / does it contradict
something" — project-wide, not per-feature-request, since two different feature requests can
still contradict or duplicate each other.

### `decisions/index.md` — flat ledger index

```markdown
# Decisions — <Project Name>

Last updated: <date>

| ID | Date | Title | Type | Feature Request | Ticket |
|---|---|---|---|---|---|
| [DEC-0001](DEC-0001_<slug>.md) | <date> | <title> | decided | [billing-export](../feature-requests/billing-export/feature-request.md) | [Linear](<url>) |
```

### `decisions/DEC-NNNN_<slug>.md` — one file per decision

One file per discussion item classified as Decided, Unresolved, Rejected, or Superseded. The
only classification that produces **no file** is `duplicate` — a reconciliation outcome (not a
classifier output) meaning this exact thing, with the same type, already exists.

```yaml
---
title: "Short decision title"
date: <date>
id: DEC-0001
feature: billing-export        # feature-request id, or null if no feature request matched
source_meeting: <slug>          # a label, not a file — no local meeting page exists to name
recording_id: <Drive file ID of the recording>    # this decision's only durable link back to the source meeting
transcript_id: <Drive file ID of the transcript>
type: decided                  # decided | unresolved | rejected | superseded
evidence_quote: "The verbatim line this decision is grounded in"
reconciliation:
  existed_before: false
  previously_rejected: false
  contradicts: []               # DEC-ids this conflicts with, if any
  on_roadmap: false
  dependencies: []               # DEC-ids or ticket ids this depends on
  changes_plan: false
supersedes: []                  # DEC-ids — only meaningful when type: superseded
linear_issue: null               # set to the issue URL once a real Linear ticket exists
---

## Statement
<The decision, one clear sentence>

## Reconciliation Notes
<1-3 sentences explaining why the reconciliation fields above were set the way they were>
```

**Status transitions**: a decision's `type` is never rewritten after creation except when a
*later* decision explicitly supersedes it — the old file gets `superseded_by: DEC-000N` added
(only then — it's absent otherwise, not pre-declared as `null`), the new file's
`supersedes: [DEC-000N]` points back. History stays intact.

---

## No Local Meeting Archive

There is no `archive/meetings/` directory and no per-meeting page under `wiki/{project-id}/`. A
meeting is a source event, not a durable artifact — its evidence lives inline on whichever
Decision Record(s) it produced (`recording_id`, `transcript_id`, `source_meeting`,
`evidence_quote`), not as a separately rendered page. A meeting-archive page would just be a
second copy of what the Decision Record and the feature's `## Key Facts` already hold.

## No Local Ticket Draft

A decision never gets a local ticket file. There is no `triage/` directory: a local draft ticket
would just duplicate content the Decision Record itself already holds (`## Statement`,
`evidence_quote`, `reconciliation`). A decision links straight to its real Linear issue
(`linear_issue`) once one exists; until then it leaves `linear_issue: null`.
