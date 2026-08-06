---
name: receiving-code-review
description: Use when you have received code review feedback on a pull request and need to respond to it. Prevents blind agreement or blind rejection. Requires verification before implementing suggestions and technical reasoning before pushing back.
---

# Receiving Code Review

## Overview

When review feedback arrives, the correct response is not immediate agreement or immediate implementation. It is investigation: verify the claim against the actual codebase, evaluate technical soundness, then act with reasoning.

**Prohibited responses:** "You're absolutely right!", "Great point!", "I'll fix that right away!" — these are performative agreement that bypass technical evaluation.

## When to Use

Use this skill whenever:
- A PR has received review comments
- A reviewer has requested changes
- You are about to implement a suggestion from a code review
- You are about to push back on a review comment

## The 5-Stage Response

### Stage 1: Read All Feedback First
Read every comment before acting on any of them. Some comments may be contradictory; some may be superseded by others. Get the full picture before implementing anything.

### Stage 2: Restate for Clarity
For each comment you are unsure about, restate what you believe the reviewer is asking. This catches misunderstandings before you write code.

### Stage 3: Check the Actual Codebase
Before implementing any suggestion, verify the claim against the current code:
- Is the issue the reviewer identified actually present?
- Does the suggested approach conflict with patterns already established in the codebase?
- Does implementing this suggestion require changes beyond the scope of the PR?

### Stage 4: Evaluate Technical Soundness
Before implementing any suggestion, check it against project conventions:

- Load the relevant sub-repo CLAUDE.md (e.g. `HealthCare/CLAUDE.md` or `HealthCare/ui/CLAUDE.md`) for architecture, patterns, and constraints
- Load the relevant rules from `.claude/rules/` (e.g. `testing-standards.md`, `general-quality.md`) for code quality and testing standards

If the suggestion conflicts with a documented convention, that is grounds to push back with a reference rather than comply.

### Stage 5: Act with Reasoning

**If the feedback is correct:** Fix it. Then verify with the appropriate command before marking it resolved.

**If the feedback conflicts with project conventions:** Explain the convention with a reference to the CLAUDE.md or rule file. Example: "Our integration test pattern uses real database containers rather than mocked repositories — see `HealthCare/CLAUDE.md`. I've kept the test as-is."

**If the feedback is ambiguous:** Ask a clarifying question rather than guessing the reviewer's intent.

**If the feedback requires a scope increase:** Flag this explicitly — "This suggestion would require changes to X, Y, Z beyond the PR scope. I'll create a follow-up ticket."

## After Implementing Fixes

For every fix based on review feedback, before pushing:

1. Run verification using the `/verification-before-completion` skill — actual command output required, not "it looks fine"
2. Use the commit format from the root `CLAUDE.md` ("Commit Message Formats" section) with a description referencing the review feedback

## Severity-Based Response Priority

Feedback from our `code-reviewer` agent and PR reviewers is categorized:

| Severity | Response |
|----------|----------|
| **BLOCKER** | Fix immediately before any other changes. Do not push back without strong technical justification and team alignment. |
| **WARNING** | Fix before the PR merges. Can be batched with other warning fixes. |
| **NOTE** | Use judgment. If the suggestion improves clarity without scope creep, implement it. If it adds complexity for marginal gain, explain why you are deferring. |

## What Not To Do

- Do not implement a suggestion and then claim "fixed" without running verification
- Do not agree with feedback and then implement something different
- Do not silently skip a comment — respond to every comment (fix, push back, or ask for clarification)
- Do not introduce new patterns or dependencies based on reviewer suggestions without checking if they conflict with project conventions
