# Code Wiki Schema

Documentation-format contract for this project's `code-wiki/`. Don't restate content that
belongs in `docs/features/` (business rules, invariants — that's the AI-context source of
truth); this tree is the human-readable rendering of the same underlying facts.

## Features/Feat-NNNN-{feature-id}/Index.md
- `Feat-NNNN` is assigned once per feature, by scanning existing `Feat-NNNN-*` directories for the
  current max and incrementing — never renumber an existing directory.
- Sections: Overview, Domain Purpose, Key Flows, Business Rules (prose, not the AI-context
  table), Entities (link to `Schemas/schemas.md#{table}`, don't restate columns), Recent Changes.

## Architecture/Overview.md
- System topology, tech stack per layer, cross-cutting architectural decisions (only ones
  recurring across 2+ features — a single feature's own decision lives in that feature's file
  instead), coupling graph.

## Schemas/schemas.md
- One row per entity, full column/constraint detail, owning `Feat-NNNN`, cross-feature FKs.
  Written once here — never duplicated per-feature.
