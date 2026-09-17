# wiki-sanitizer

The security boundary of the pipeline. Every item, regardless of source, passes through here
before any LLM-judgment step (summarizing, classifying, mapping) touches it.

## Input

`{ id, source, raw_text }` from `wiki-local-scanner.md` / `wiki-transcript-reader.md`.

## Steps

1. **Strip unsafe markup.** Remove `<script>`, `<style>`, and any embedded HTML/executable-looking
   content. Meeting notes are plain text by nature — anything that looks like markup or code
   injection is noise or an attack, not content, and gets stripped rather than interpreted.
2. **Redact secret-shaped strings.** Pattern-match and replace with `[REDACTED]`: API keys
   (`sk-...`, `AKIA...`), bearer tokens, anything that looks like a password shared out loud
   ("the password is..."), connection strings, private key blocks (`-----BEGIN...KEY-----`).
   Err toward over-redacting — a false-positive redaction loses a little context; a missed secret
   leaks into a wiki file that may get published to a public PR.
3. **Enforce the size cap.** If the text exceeds 50,000 characters, truncate and note the
   truncation explicitly (`[TRUNCATED — original length: N chars]`) rather than silently cutting
   it — a downstream summarizer working from a silently-truncated transcript could report
   confidently on content that was actually cut off.
4. **Wrap as evidence.** Mark the final text as `[EVIDENCE]` — every downstream step that quotes
   from it (`evidence_quote` fields, etc.) is quoting from this sanitized version, never the raw
   input.

## Output

`{ id, source, sanitized_text, was_truncated: bool }`

## Rules

- This step runs on **every** item, no exceptions — never let a "trusted" source (e.g. a known
  Drive folder) skip sanitization.
- Redaction is one-way and irreversible for this item — a redacted secret cannot be un-redacted
  later in the pipeline.
- Never let sanitization silently drop entire sections without the `[TRUNCATED]` marker — downstream
  steps need to know when their view of the source is incomplete.
