---
feat_id: Feat-0003
feature: llm-extraction-inference
type: backend-service
domain: llm-inference
criticality: medium
touched_paths:
  - llm/
  - mlx_adapter/
  - scripts/convert_to_mlx.py
depends_on: []
consumed_by: [Feat-0001, Feat-0006]
implements: []
tags: [llm, inference, extraction, mlx]
---

## Overview

| Field | Value |
|---|---|
| Type | backend-service |
| Package | `llm/` |
| Path | `llm/*.py`, `mlx_adapter/`, `scripts/convert_to_mlx.py` |
| Domain | llm-inference |
| Last updated | 2026-09-17 |

## Domain Purpose

Two independent LLM-backed capabilities live here: extracting structured drug/adverse-drug-event
data from clinical text (a local, MLX-quantized model on Apple Silicon), and generating a cited,
natural-language answer to a user's search query (a call to Anthropic's Claude API). Neither
depends on the other.

## Invariants

- The MLX model + its LoRA adapter must both load successfully before the extraction server
  (`llm/ade_api.py`) will start; it does not start in a degraded/partial state.
- `AdeModel.loaded` only ever transitions False → True, once, at server startup — the model is
  never unloaded or reloaded while the process runs.
- ADE extraction output is capped at 150 tokens; Claude RAG answers at 1024 tokens.

## Access Control

**Model**: none. Neither `/extract` nor `/health` has any authentication.

| Action | Access Condition | Enforced In |
|---|---|---|
| Call `POST /extract` | *none* | — |
| Call `GET /health` | *none* | — |

This is acceptable only insofar as the ADE server is assumed to be reachable solely from
`localhost:8001` by trusted in-cluster callers (Feat-0001's `ExtractionWorker`) — it has no
defenses if exposed more broadly. Flag any change that makes this port reachable externally.

## Business Rules

| BR-NN | Rule | Enforced In | Severity |
|---|---|---|---|
| BR-01 | Empty sentence to `/extract` → HTTP 422 | `llm/ade_api.py:56-57` | LOW |
| BR-02 | Inference before model load → `RuntimeError` | `llm/ade_model.py:62-63` | MEDIUM |
| BR-03 | Malformed model JSON output → returned verbatim in the response's `raw` field, `drug`/`adverse_effect` set to null rather than raising | `llm/ade_model.py:81-90` | MEDIUM |
| BR-04 | Missing Anthropic API key → a placeholder error string is returned as the "answer" instead of raising | `llm/claude_client.py:39-44` | MEDIUM |
| BR-05 | Citation indices are parsed from `[N]` markers in the Claude response; malformed markers (`[1a]`, out-of-range `[999]`) are silently dropped, not surfaced as an error | `llm/claude_client.py:80-81` | LOW |

## External Integrations

| System | Trigger | What Happens |
|---|---|---|
| Anthropic Claude API | `ui/search_page.py` calls `generate_answer()` after retrieval | Sends retrieved chunks + query, gets back a cited answer; API key missing/invalid → placeholder string, not an exception |
| MLX-quantized Qwen2.5-7B + LoRA adapter (`mlx_adapter/`) | `ade_api.py` server startup | Loaded once into memory; `scripts/convert_to_mlx.py` is the one-time offline conversion script that produced this adapter |

## Safe vs Dangerous Changes

### Safe
- Adjusting `max_tokens` for either the ADE extraction or the Claude RAG call.
- Adding new injection-pattern regexes to the caller side (Feat-0004 owns guardrails, not this feature).

### Dangerous — Requires Review
| Change | Risk | Why |
|---|---|---|
| Adding auth to `/extract`/`/health` without updating `ExtractionWorker`'s call | Breaks the pipeline if the new auth isn't also added to the caller | No shared client wrapper exists between the two — the HTTP call is hand-rolled in `extraction_worker.py` |
| Changing the `/extract` request/response shape | Breaks `ExtractionWorker` (Feat-0001) silently — no schema versioning | Contract is implicit, not versioned |

### Human Escalation Required
- Exposing port 8001 outside localhost — there is currently no authentication to fall back on.

## Known Error Scenarios

| Scenario | Error Returned | Root Cause |
|---|---|---|
| MLX model or adapter path missing at startup | Server fails to start (`FileNotFoundError`) | `llm/ade_model.py:44-53` |
| ADE API unreachable from `ExtractionWorker` | No error to the caller — extraction skipped for that sentence, pipeline continues (see Feat-0001 BR-06) | `workers/extraction_worker.py:61-66` |
| Claude API error (timeout, rate limit, auth) | Logged; error string returned to the search page as if it were the answer | `llm/claude_client.py:85-87` |

## Testing Expectations

- *Open question: no dedicated test file for `llm/` was found under `tests/unit/` — model-load failure, malformed-JSON fallback, and Claude-API-error paths do not appear to have direct test coverage.*

## Forbidden Patterns

- Never assume `/extract` or `/health` are safe to expose beyond localhost without adding authentication first.
- Never let a Claude API failure raise an unhandled exception into the UI — it must degrade to a visible error message (current behavior; preserve it).

## Key Files

- `llm/ade_api.py` — FastAPI server (`/extract`, `/health`), request validation, model lifespan
- `llm/ade_model.py` — MLX model loading, chat templating, inference, JSON-parse fallback
- `llm/claude_client.py` — Anthropic API client, prompt construction (includes caller role for audit context, not for access control), citation-index parsing
- `mlx_adapter/adapter_config.json` — LoRA hyperparameters (rank=8, alpha=16.0)
- `scripts/convert_to_mlx.py` — one-time base-model quantization + adapter conversion (not run at request time)

## Context Routing

| Feature | Load when |
|---|---|
| Feat-0001 (Async Processing Workers) | changing the `/extract` contract or its failure handling |
| Feat-0006 (Healthcare UI) | changing `generate_answer()`'s signature or citation format |

| Workflow | Sections to load |
|---|---|
| Change the extraction request/response shape | Business Rules, Known Error Scenarios, Key Files |
| Add auth to the ADE server | Access Control, Safe vs Dangerous Changes |
