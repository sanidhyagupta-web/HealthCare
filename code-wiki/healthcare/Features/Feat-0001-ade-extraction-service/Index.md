---
feat_id: Feat-0001
feature: ade-extraction-service
type: backend-service
domain: clinical-nlp
criticality: low
touched_paths:
  - llm/ade_api.py
  - llm/ade_model.py
depends_on: []
consumed_by: [Feat-0004-pipeline-workers]
implements: []
tags: [nlp, extraction, ml-inference, standalone-service]
---

## Overview

| | |
|---|---|
| Type | backend-service (standalone FastAPI microservice, separate process) |
| Package | `llm/` (2 of 4 files — see [[Feat-0005-semantic-search-qa]] for `llm/claude_client.py`) |
| Path | `llm/ade_api.py`, `llm/ade_model.py` |
| Domain | Adverse Drug Event (ADE) extraction from clinical text |
| Last updated | initial scan |

## Domain Purpose

Extracts structured `(drug, adverse_effect)` pairs from a single sentence of clinical text, using
a fine-tuned local LLM, so the ingestion pipeline can surface adverse-drug-event signals from
unstructured notes without sending patient text to an external API.

## Status / State Machine

None — stateless request/response API. The only lifecycle is the model itself: unloaded until
`lifespan()` calls `_model.load()` at process startup; every request after that is served from
the one in-memory model instance.

## Invariants

- The model and tokenizer are loaded exactly once, at startup, and shared across all requests —
  there is no per-request model reload.
- `extract()` raises `RuntimeError` if called before `load()` completes.
- A response's `drug`/`adverse_effect`/`sentence`/`raw` fields are all `Optional[str]` — a
  non-JSON model output still returns 200, with the raw text in `raw` instead of failing the request.

## Access Control

**Model**: none. Both endpoints are open to any caller that can reach the port.

| Action | Access Condition | Enforced In |
|---|---|---|
| `POST /extract` | none | — |
| `GET /health` | none | — |

## Business Rules

| BR-NN | Rule | Enforced In | Severity |
|---|---|---|---|
| BR-01 | `sentence` must be non-empty/non-whitespace | `llm/ade_api.py` (`extract()` handler) | MEDIUM |
| BR-02 | Model output that isn't valid JSON is returned verbatim in `raw` rather than failing | `llm/ade_model.py` | LOW |
| BR-03 | `extract()` called before `load()` raises `RuntimeError`, not a silent no-op | `llm/ade_model.py` | MEDIUM |
| BR-04 | Model/adapter files must exist at startup or the process fails to boot (`FileNotFoundError`, points at `scripts/convert_to_mlx.py`) | `llm/ade_model.py` | HIGH |

## External Integrations

| System | Trigger | What Happens |
|---|---|---|
| Qwen2.5-7B + QLoRA adapter (`mlx_adapter/`, local MLX inference) | every `/extract` call | 4-bit quantized generation on Apple Silicon (MPS), no CUDA/GPU server needed |
| [[Feat-0004-pipeline-workers]] `ExtractionWorker` | per-sentence, during the async ingestion pipeline | HTTP `POST http://localhost:8001/extract` (`ADE_API_URL` env var) |

## API Endpoints

| Method | Path | Auth | Who Uses It | Description |
|---|---|---|---|---|
| POST | `/extract` | none | [[Feat-0004-pipeline-workers]] `ExtractionWorker` | `{"sentence": str}` → `{drug, adverse_effect, sentence, raw}` |
| GET | `/health` | none | *unknown — no caller found in scanned paths* | `{"status": "ok", "model_loaded": bool}` |

## Safe vs Dangerous Changes

### Safe
- Adjusting the extraction prompt template inside `ade_model.py` (no downstream contract change as long as the response shape is preserved)
- Adding new optional response fields

### Dangerous — Requires Review
| Change | Risk | Why |
|---|---|---|
| Renaming/removing `drug`, `adverse_effect`, `sentence`, or `raw` from `ExtractResponse` | Breaks [[Feat-0004-pipeline-workers]] `ExtractionWorker`, which reads these fields by name over HTTP with no schema versioning | 
| Changing the default port (8001) or route path | Breaks the hardcoded `ADE_API_URL` default in `ExtractionWorker` |

### Human Escalation Required
- Adding authentication to this service, since [[Feat-0004-pipeline-workers]]'s caller currently sends no credentials at all — a coordinated change is needed on both sides.

## Known Error Scenarios

| Scenario | Error Returned | Root Cause |
|---|---|---|
| Empty/whitespace sentence | 422 Unprocessable Entity | explicit validation in the handler |
| Model not loaded | 500 (`RuntimeError`) | called before `lifespan()` startup completed |
| Model/adapter file missing at boot | process fails to start | `FileNotFoundError` |
| Model output not JSON | 200, with `raw` populated and `drug`/`adverse_effect` null | graceful degradation, not an error |
| Caller-side: connection refused/timeout | *(not this service — see [[Feat-0004-pipeline-workers]])* | ExtractionWorker catches and logs, continues without extraction for that sentence |

## Testing Expectations

*Open question: no tests found for `llm/ade_api.py` or `llm/ade_model.py` in `tests/unit/` — this
service currently has zero test coverage.*

## Key Files

- `llm/ade_api.py` — FastAPI app, 2 endpoints, model lifespan management
- `llm/ade_model.py` — `AdeModel` class: MLX model/adapter loading, prompt construction, JSON-or-raw response parsing

## Context Routing

| Feature | Load when |
|---|---|
| Feat-0001-ade-extraction-service | touching `/extract` request/response shape, the extraction prompt, or MLX model loading |

## Forbidden Patterns

- Never assume the ADE API is always reachable from the caller side — [[Feat-0004-pipeline-workers]] treats every failure mode (connection error, timeout, bad JSON) as "skip this sentence's extraction," not as a pipeline failure. Don't make extraction failures fatal to document processing without updating that contract deliberately.

## Architectural Decisions

| Decision | Reason | Do Not Change Without |
|---|---|---|
| Run as a separate process/port rather than in-process with the FastAPI ingestion app | Isolates a heavyweight local-model load (Qwen2.5-7B) from the lightweight ingestion API's process lifecycle | Coordinating a change to `ADE_API_URL` on the caller side |
