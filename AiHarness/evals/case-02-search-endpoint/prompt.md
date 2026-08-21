# Eval Case 02 — Prompt

Paste this verbatim into a fresh Claude Code / Cursor session after loading `AiHarness/Agents.md`.

---
Firstly read `Agents.md`.

Add a FastAPI endpoint `POST /search` that accepts a JSON body `{"query": string, "role": string}` and returns the top 5 matching chunks with citations and an LLM-generated answer.

The endpoint must:
- Validate that `role` is a known role in the system.
- Retrieve candidates using both vector search (Chroma) and keyword search (BM25).
- Merge results with RRF and rerank with the cross-encoder.
- Filter results by the caller's role before sending to the LLM.
- Generate an answer using `llm/claude_client.py` with inline `[N]` citations.
- Emit an audit log entry for the query, including the role and result chunk IDs (not raw text).
- Return a JSON response: `{"answer": string, "sources": [{"chunk_id", "source_file", "source_section", "page"}]}`.

Add this to the existing `app/main.py`.

Build this feature.

After building this feature compare the output with `expected.md` and write down the results in `result-notes.md`.