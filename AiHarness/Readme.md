# Harmony AI Harness

This folder contains the AI harness for the Healthcare Semantic Search / Harmony replica project.

## How to Use

1. Copy this folder into the root of your project.
2. Open a fresh Cursor or Claude Code chat.
3. Ask the coding tool to read `agents.md`.
4. Pick an eval prompt from `/evals`.
5. Let the tool create a feature folder, fill templates, and implement.
6. Compare against `expected.md`.
7. Update skills when the tool makes the same mistake twice.

## Suggested First Cursor Prompt

```text
Read agents.md. Then run the eval in evals/case-01-add-top5-search-endpoint/prompt.md.
Create the feature folder, fill the three templates, and implement only after the implementation plan is complete.
```
