---
feat_id: Feat-0004
feature: llm
type: backend-service
domain: model-inference
criticality: medium
touched_paths:
  - llm/ade_api.py
  - llm/ade_model.py
  - llm/claude_client.py
depends_on: [platform]
consumed_by: [ui, workers]
implements: []
tags: [llm, mlx, claude, extraction]
---

## Overview

| Type | Package | Path | Domain | Last updated |
|---|---|---|---|---|
| backend-service | `llm` | `llm/` | LLM inference — local ADE extraction server + Claude API client | 2026-09-17 (initial scan) |

## Domain Purpose

Two independent LLM integrations: a standalone local inference server (`ade_api.py`, MLX-based) that
extracts drug/adverse-effect pairs from clinical sentences, and a thin Claude API client used for
RAG answer generation over retrieved chunks.

## Invariants

- `AdeModel` is a process-scoped singleton; state is lost on restart or scale-out (`llm/ade_model.py`).
- Citation indices returned by `generate_answer()` are parsed as 1-based and must fall within the
  bounds of the supplied `context_chunks` list (`llm/claude_client.py:80-81`).

## Access Control

**Model**: none. `ade_api.py`'s `POST /extract` and `GET /health` have **no authentication** —
anyone who can reach `http://localhost:8001` (or wherever it's deployed) can call them.

| Action | Access Condition | Enforced In |
|---|---|---|
| `POST /extract` | none found | `llm/ade_api.py` |
| `generate_answer()` (Claude) | requires `ANTHROPIC_API_KEY` to be configured | `llm/claude_client.py:39-44` |

## Business Rules

| BR-NN | Rule | Enforced In | Severity |
|---|---|---|---|
| BR-01 | Extraction input sentence must not be empty | `llm/ade_api.py:56-57` | LOW |
| BR-02 | Model must be `load()`ed before `extract()` is called | `llm/ade_model.py:62-63` | MEDIUM |
| BR-03 | Malformed inference JSON degrades gracefully to raw text rather than raising | `llm/ade_model.py:81-90` | LOW |
| BR-04 | No context chunks → a fixed "no relevant records found" response, no LLM call made | `llm/claude_client.py:46-47` | LOW |
| BR-05 | Missing API key → a fixed error string, no LLM call made | `llm/claude_client.py:39-44` | MEDIUM |

## External Integrations

| System | Trigger | What Happens |
|---|---|---|
| MLX local inference (Apple-silicon) | FastAPI `lifespan` startup, `/extract` calls | loads adapter/model artifacts from `mlx_model/`/`mlx_adapter/` once at boot |
| Anthropic Claude API | `generate_answer()` | HTTP call to `anthropic.Anthropic().messages.create()`; any exception is caught, logged, and returned as an error string rather than raised |

## API Endpoints

| Method | Path | Auth | Who Uses It | Description |
|---|---|---|---|---|
| POST | `/extract` | none | [[workers]] `ExtractionWorker` via HTTP (`ADE_API_URL`, default `http://localhost:8001`) | drug/adverse-effect extraction from one sentence |
| GET | `/health` | none | — | liveness check |

## Safe vs Dangerous Changes

### Safe
- Adjusting the Claude prompt/response parsing as long as the citation-index contract is preserved.

### Dangerous — Requires Review
| Change | Risk | Why |
|---|---|---|
| Changing `ade_api`'s `/extract` response shape (`drug`, `adverse_effect` fields) | Breaks `ExtractionWorker` silently at runtime | It's an HTTP call with no schema contract/versioning between the two processes |
| Exposing `ade_api.py` beyond localhost without adding auth | Unauthenticated inference endpoint reachable externally | No auth exists today |

### Human Escalation Required
- Deploying `ade_api.py` anywhere reachable outside the local host, given it has zero authentication.

## Known Error Scenarios

| Scenario | Error Returned | Root Cause |
|---|---|---|
| Empty sentence | HTTP 422 | `ExtractRequest` validation |
| Model files missing on disk | `FileNotFoundError` with a conversion-script hint | `llm/ade_model.py:44-53` |
| `extract()` called before `load()` | `RuntimeError` | `llm/ade_model.py:62-63` |
| Claude API/network failure | tuple `("LLM unavailable: {exc}", [])`, error logged | `llm/claude_client.py:85-87`, broad `except Exception` |
| Anthropic API key not configured | tuple with a fixed configuration-error message | `llm/claude_client.py:39-44` |

## Forbidden Patterns

- Never assume `ade_api.py`'s response schema is stable without checking `ExtractionWorker`'s parsing.

## Key Files

- `llm/ade_api.py` — FastAPI inference server (`/extract`, `/health`)
- `llm/ade_model.py` — MLX model wrapper, singleton load/extract
- `llm/claude_client.py` — Anthropic client, `generate_answer()`

## Context Routing

| Feature | Load when |
|---|---|
| Feat-0004-llm | touching drug/ADE extraction or Claude-based answer generation |

| Workflow | Sections to load |
|---|---|
| Debugging a bad/missing extraction | Known Error Scenarios, External Integrations |
| Changing the answer-generation prompt | Business Rules BR-04/BR-05, API Endpoints |
