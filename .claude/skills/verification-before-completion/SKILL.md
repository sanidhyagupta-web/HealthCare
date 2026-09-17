---
name: verification-before-completion
description: Use before claiming any task, fix, or implementation is complete. Enforces evidence-based completion — no "should work" or "probably" claims. Run fresh verification commands and read actual output before declaring done.
---

# Verification Before Completion

## Overview

A task is not complete until you have run a verification command AND read the output confirming it passed. Reporting completion based on confidence, prior results, or agent reports is prohibited.

**Absolute rule: NO COMPLETION CLAIMS WITHOUT FRESH VERIFICATION EVIDENCE.**

## When to Use

This skill applies whenever you are about to:
- Say a task is complete
- Say a bug is fixed
- Say tests pass
- Say a build succeeds
- Say requirements are fulfilled
- Hand off to the next phase of the workflow

## The Verification Sequence

1. **Identify the verification command** for what you are claiming is complete
2. **Run it fresh** — prior runs do not count; the codebase may have changed
3. **Read the full output** — exit code AND content, not just "no errors appeared"
4. **Confirm the output supports the claim** — a passing build does not mean tests pass; a green test run does not mean the right tests ran
5. **Only then make the claim**

## Project Verification Commands

### Per-task verification (during implementation)

Run after each task, before committing.

<!-- CUSTOMIZE: Replace these with your project's actual verification commands.
     Examples are illustrative; the principle is the same: format, compile/typecheck, run relevant tests, and capture the output. -->

```bash
# Backend (illustrative — adapt to your stack)
<your-build-tool> format        # Fix formatting first
<your-build-tool> compile       # Compilation/typecheck must pass
<your-build-tool> test <test-class-or-pattern>  # Relevant tests only

# Frontend — run on changed files only (illustrative — adapt to your tooling)
<your-linter> <changed-files>             # Must produce no errors
<your-formatter> --write <changed-files>  # Fix formatting
<your-typechecker> <changed-files>        # Zero type errors
```

**What does NOT count:**
- "The code looks correct"
- "I ran it earlier and it passed"
- "The logic is the same as the working version"
- A subagent reporting success without a commit hash or command output

### Post-implementation verification (before PR creation)

Use the `/post-checks` skill — it runs the full suite (tests, spotless, spotbugs, build) across all affected services and apps and produces a verified summary.

## Language That Signals Missing Verification

If you find yourself writing any of the following, STOP and run verification first:

- "This should work now"
- "The fix looks correct"
- "Tests should pass"
- "It's probably working"
- "The implementation seems complete"
- "I believe this resolves the issue"

Replace these with actual command output.

## Partial Verification Is Not Verification

| Situation | What you might think | What is actually verified |
|-----------|---------------------|--------------------------|
| Compilation passes | Everything is fine | Only that the code compiles |
| One test passes | The feature works | Only that one test case |
| Formatting passes | Code quality is fine | Only that formatting rules are met |
| No TypeScript errors | App will run correctly | Only that types are correct |

Always match the verification scope to the completion claim scope.

## Verification at Different Workflow Stages

### During task implementation (backend-implementer / frontend-implementer)
Run per-task verification after each task before committing. See the agent's "After Each Change" section for the exact commands. If verification fails, invoke the `systematic-debugging` skill — do not retry the same fix or push through a failing check.

### During post-checks (/post-checks skill)
Run the full suite for all affected services/apps. This is the macro-level gate before PR creation.

### After receiving review feedback
After fixing a review comment, re-run the relevant verification command before marking the fix as done. Do not just push the commit — confirm the check passes. If the check fails, invoke `systematic-debugging` before attempting another fix.
