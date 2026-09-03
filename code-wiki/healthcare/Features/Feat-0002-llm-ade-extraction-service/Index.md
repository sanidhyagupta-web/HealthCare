---
feat_id: Feat-0002
feature: llm-ade-extraction-service
type: backend-service
domain: llm-inference
criticality: medium
touched_paths:
  - llm/
  - mlx_adapter/
  - evaluation/
depends_on: []
consumed_by: [Feat-0001]
implements: []
tags: [llm, inference, ade-extraction, eval]
---

## Overview

| Type | Package | Path | Domain | Last updated |
|---|---|---|---|---|
| backend-service | (single package) | `llm/`, `mlx_adapter/`, `evaluation/` | Adverse-drug-event extraction inference | 2026-09-03 |

## Domain Purpose

A standalone inference microservice that takes a single clinical sentence and extracts a
mentioned drug and its adverse effect, using a 4-bit-quantized Qwen2.5-7B model with a QLoRA
adapter (via `mlx-lm`, Apple Silicon-only). Runs as a separate `uvicorn` process on port 8001,
called by the ingestion pipeline's `ExtractionWorker`. `llm/claude_client.py` is a *different*
concern living in the same directory — the Claude-based RAG answer generator used by
[Feat-0003](../Feat-0003-search-retrieval/Index.md)'s search UI, not part of ADE extraction.

## Status / State Machine

None found — stateless per-request inference, except a module-level "is the model loaded" flag
set once at process startup via FastAPI's `lifespan`.

## Invariants

- The model is loaded exactly once, at server startup, into a process-scoped singleton
  (`llm/ade_api.py`). It is never reloaded or hot-swapped.
- `extract()` raises `RuntimeError` if called before `load()` completes.

## Access Control

**Model**: None. `POST /extract` and `GET /health` have no authentication, no rate limiting, and
no authorization check of any kind — anyone who can reach port 8001 can call them.

| Action | Access Condition | Enforced In |
|---|---|---|
| `POST /extract` | none | *(no enforcement found)* |
| `GET /health` | none | *(no enforcement found)* |

## Business Rules

| BR | Rule | Enforced In | Severity |
|---|---|---|---|
| BR-01 | Empty/whitespace-only sentence → HTTP 422 | `llm/ade_api.py` | MEDIUM |
| BR-02 | Model must be loaded before inference, else `RuntimeError` | `llm/ade_model.py` | HIGH |
| BR-03 | Missing model/adapter files at startup → `FileNotFoundError` (fails loud) | `llm/ade_model.py` | HIGH |
| BR-04 | Response capped at 150 generated tokens | `llm/ade_model.py` | LOW |
| BR-05 | Malformed JSON from the model → returned as `raw` text with `drug`/`adverse_effect` = null, not an error | `llm/ade_model.py` | MEDIUM |

## External Integrations

| System | Trigger | What Happens |
|---|---|---|
| [Feat-0001](../Feat-0001-document-ingestion-pipeline/Index.md) `ExtractionWorker` | per sentence during extraction stage | `POST http://localhost:8001/extract`, 30s timeout, no auth; connection failure logs a warning and the pipeline continues without that sentence's extraction |

## API Endpoints

| Method | Path | Auth | Who Uses It | Description |
|---|---|---|---|---|
| POST | `/extract` | none | Feat-0001 `workers/extraction_worker.py` | `{sentence}` → `{drug, adverse_effect, sentence, raw}` |
| GET | `/health` | none | *(no caller found in repo — likely ops/monitoring only)* | `{status, model_loaded}` |

## Safe vs Dangerous Changes

### Safe
- Adjusting `max_new_tokens` or the system prompt's exact wording.
- Adding a new eval metric to `evaluation/run_eval.py` / `AiHarness/evals/run_qwen_eval.py`.

### Dangerous — Requires Review
| Change | Risk | Why |
|---|---|---|
| Changing the `{drug, adverse_effect, sentence}` JSON response shape | Breaks `ExtractionWorker`'s parsing silently | No shared schema/contract test between the two services |
| Adding auth to `/extract` | Could break `ExtractionWorker` if not updated in lockstep | They're deployed/versioned independently today |

### Human Escalation Required
- Deciding whether `/extract` needs authentication at all — it currently trusts network placement (localhost) as its only boundary.

## Known Error Scenarios

| Scenario | Error Returned | Root Cause |
|---|---|---|
| Empty sentence | HTTP 422, "sentence must not be empty" | input validation |
| Model not loaded | `RuntimeError` | called before `load()` |
| Missing model/adapter files | `FileNotFoundError` with conversion-script hint | ops/setup issue |
| Connection refused/timeout from caller | caller (`ExtractionWorker`) logs warning, returns `(None, None)`, pipeline continues | service down or overloaded |

## Testing Expectations

- `evaluation/run_eval.py` and `AiHarness/evals/run_qwen_eval.py` measure `json_validity`,
  `schema_validity`, `drug_exact_match`, `ade_exact_match`, `overall_exact_match`, and
  `hallucination_rate` against `evaluation/test_dataset.json`, compared against a Claude API
  baseline. Not integrated into CI — run manually.
- No integration test found exercising `POST /extract` over HTTP.

## Forbidden Patterns

- Never assume `/extract` is reachable synchronously without a timeout — callers must degrade gracefully (as `ExtractionWorker` does today).

## Key Files

- `llm/ade_api.py` — FastAPI app, `POST /extract`, `GET /health`, model lifecycle (`lifespan`)
- `llm/ade_model.py` — `AdeModel` class: `load()`, `extract()`, prompt template, JSON parsing
- `llm/claude_client.py` — unrelated: Claude RAG answer generation for Feat-0003, not ADE extraction
- `mlx_adapter/adapter_config.json` — QLoRA adapter config (rank=8, alpha=16.0)
- `evaluation/run_eval.py`, `evaluation/test_dataset.json` — eval harness
- `scripts/convert_to_mlx.py` — one-time model/adapter quantization + conversion (Flight Deck tooling, not part of the running service)

## Context Routing

| Feature | Load when |
|---|---|
| Feat-0002 | touching `/extract` request/response shape, the model prompt, or the eval harness |
| Feat-0001 | touching how `ExtractionWorker` calls this service or handles its failure |

*Open question: is `/extract` intended to ever be reachable from outside localhost (e.g. a
separate host/container in production), and if so, should it gain authentication before that
happens?*

*Open question: `GET /health` has no caller found anywhere in this repo — is it consumed by an
external ops/monitoring system not visible here, or is it unused?*
