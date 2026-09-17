# Code Wiki Schema

Documentation-format contract for this project's `code-wiki/`. **This tree is the source of
truth about the codebase** — business rules, invariants and entity definitions live here and
are not a rendering of anything else. Write for the agent about to change this code, not for
a reader browsing documentation.

## Frontmatter (every Features/*/Index.md)

```yaml
feat_id: Feat-NNNN          # canonical, assigned once, never renumbered
feature: {slug}             # kebab-case name; may change without changing feat_id
type: backend-service | frontend-feature | shared-library
domain: {business-domain}
criticality: high | medium | low
touched_paths:              # the source paths this feature owns
  - {path}
depends_on: [{feat_id or slug}, ...]      # edges are canonical HERE
consumed_by: [{feat_id or slug}, ...]
implements: [FR-*, ...]     # bridge to product intent in wiki/; [] if none known
tags: [{domain-tag}, {capability-tag}]
```

`depends_on`/`consumed_by` are the **only** authoritative record of the dependency graph.
`Features/index.md` and the coupling graph in `Architecture/Overview.md` are generated views
of these fields — never hand-maintain an edge in either, and never let one disagree.

## Features/Feat-NNNN-{feature-id}/Index.md

`Feat-NNNN` is assigned once per feature by scanning existing `Feat-NNNN-*` directories for
the current max and incrementing. **Never renumber an existing directory** — a rename changes
`feature`, never `feat_id`.

**Line budget: 400 lines.** When tight, omit in this order:
- **Optional, omit first** — Status/State Machine, External Integrations, Architectural Decisions
- **Recommended, omit only if forced** — Entities Owned, User Roles, Forbidden Patterns, Testing Expectations, Known Error Scenarios
- **Required, never omit** — Domain Purpose, Invariants, Business Rules, Safe vs Dangerous Changes, Key Files, Context Routing

Prefer tables over prose, one-line descriptions, and at most the top 8 business rules.

Sections, for `type: backend-service` and `shared-library`:

| Section | Form |
|---|---|
| Overview | table: Type, Package, Path, Domain, Last updated |
| Domain Purpose | 1–2 sentences on the business problem. No file paths or library names — those are Key Files |
| Entities Owned | table: Entity → link to `../../Schemas/schemas.md#{table}` → what it represents. **Never restate columns** — `Schemas/schemas.md` holds them once |
| Status / State Machine | table: Status, Business Meaning, Can Transition To, Trigger; plus transition constraint bullets |
| Invariants | bullets. Non-negotiable guarantees an agent must never violate |
| Access Control | `**Model**:` line, then table: Action, Access Condition, Enforced In |
| Business Rules | table: `BR-NN`, Rule, Enforced In (`file:line`), Severity. Severity is `CRITICAL` (data-integrity/security invariant), `HIGH` (real business impact), `MEDIUM` (operational), `LOW` (quality) |
| External Integrations | table: System, Trigger, What Happens — includes async processes (scheduled jobs, queue consumers, webhooks) |
| API Endpoints | table: Method, Path, Auth, Who Uses It, Description |
| Safe vs Dangerous Changes | `### Safe` bullets; `### Dangerous — Requires Review` table (Change, Risk, Why — who breaks and how); `### Human Escalation Required` bullets |
| Known Error Scenarios | table: Scenario, Error Returned, Root Cause |
| Testing Expectations | required test types, plus critical-assertion bullets |
| Architectural Decisions | table: Decision, Reason, Do Not Change Without. Only this feature's own — recurring ones belong in `Architecture/Overview.md` |
| Forbidden Patterns | bullets: `Never {pattern} — {reason}` |
| Key Files | bullets: `path — role` |
| Context Routing | optional-load table (Feature, Load when) and a per-workflow section-loading table |

For `type: frontend-feature`, replace API Endpoints / Entities Owned / Status with:

| Section | Form |
|---|---|
| What This Does for the User | 1–2 sentences, user-facing |
| Key User Flows | per flow: the user action and what happens |
| UI States | table: Condition, What Renders — including domain-meaning states (a limit exceeded, an archived record) |
| APIs Consumed | table: Method, Path, Owning `Feat-NNNN` |
| State | the store slice, its shape, and its exported selectors |

A section with nothing found writes `*None found.*` — never a plausible guess. A section
whose answer could not be determined writes `*Open question: {the question}.*` See the
"unknowns" rule below.

## Features/index.md — GENERATED

Regenerated from frontmatter; never hand-edited. Holds:
- **Feature Catalog** — one table per `type`: `feat_id`, feature, domain, criticality, path
- **Workflow Routing Rules** — the keyword → feature-file table, and the per-workflow
  section-loading table. This is how a consumer avoids loading the whole tree
- **Dependency Graph** — mandatory dependencies and downstream impact, derived from
  `depends_on`/`consumed_by`

## Architecture/Overview.md

System topology, tech stack per layer, cross-cutting architectural decisions (only those
recurring across 2+ features — a single feature's own decision lives in that feature's file),
and the coupling graph rendered from frontmatter edges.

## Schemas/schemas.md

One entry per entity: full column list (name, type, nullability, default), constraints
(unique/check/exclusion/FK) with the migration that introduced each, the owning `Feat-NNNN`,
and foreign keys that cross feature boundaries. **Written once here, never duplicated
per-feature** — a feature links to an anchor in this file instead.

Where a migration and an application-level schema definition disagree, **the migration is the
truth** and the disagreement is recorded as a finding.

## Unknowns

Never fabricate. A fact the scan could not establish is written as
`*Open question: {the question}.*` in the section where it belongs. An explicit open question
is a useful artifact; an invented answer is indistinguishable from a real one and silently
poisons every consumer downstream.
