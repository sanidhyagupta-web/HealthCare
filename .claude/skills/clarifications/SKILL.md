---
name: clarifications
description: Process clarification answers and update the requirements document. Run after filling in clarifications.md.
disable-model-invocation: true
---

# Update Requirements After Clarifications

The user has answered the clarification questions. Update the requirements document to incorporate their answers.

## Steps

1. **Find the execution folder**: Search `docs/execution/*/clarifications.md` for the most recently modified one (or use the active workflow's folder).

2. **Read `clarifications.md`**: Parse all questions and their answers.

3. **Validate answers**: Check that all questions have been answered. If any are blank (`_[fill in]_`), list the unanswered questions and ask the user to complete them.

4. **Update `requirements.md`**:
   - Incorporate each answer into the relevant section
   - Remove corresponding entries from "Open Questions"
   - Add new detail to appropriate sections
   - If an answer introduces new scope, add it; if it narrows scope, update accordingly

5. **Update `clarifications.md`**:
   - Change status to `RESOLVED`
   - Keep questions and answers as audit trail

6. **Check for new questions**: If answers reveal new ambiguities:
   - Add new questions to `clarifications.md` (numbered continuing from last)
   - Set status to `PARTIAL` instead of `RESOLVED`
   - Inform the user about new questions

7. **Inform the user**:
   - Summarize what was updated
   - If all resolved: tell them to proceed to `/plan`
   - If new clarifications: tell them to answer and run `/clarifications` again

## Rules

- Do NOT add implementation details
- Preserve the document structure
- If an answer contradicts existing requirements, flag the contradiction
- Never delete questions or answers from `clarifications.md`
