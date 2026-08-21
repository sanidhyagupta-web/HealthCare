# Architecture Overview

## System Topology

A single Python monorepo, not a microservices architecture in the conventional sense — one
Streamlit process, one primary FastAPI process, and one standalone FastAPI microservice, sharing
a filesystem/SQLite/S3 persistence layer and communicating either in-process (function calls) or
over unauthenticated localhost HTTP.

```
┌─────────────────────────┐
│   Feat-0006             │   the only human-facing surface
│   streamlit-ui           │   (Streamlit, single process, port 8501 by default)
└──────────┬───────────────┘
           │ in-process function calls (no HTTP, no API client layer)
           ▼
┌─────────────────────────┐     ┌──────────────────────────┐
│ Feat-0003                │────▶│ Feat-0004                │
│ document-ingestion        │     │ pipeline-workers          │
│ (FastAPI app, port 8000?) │     │ (daemon threads, in-proc  │
│ + filesystem watcher      │     │  queue.Queue chain)       │
└──────────┬────────────────┘     └──────────┬────────────────┘
           │                                  │  HTTP (unauthenticated)
           │                                  ▼
           │                       ┌──────────────────────────┐
           │                       │ Feat-0001                 │
           │                       │ ade-extraction-service     │
           │                       │ (standalone FastAPI,       │
           │                       │  port 8001, local MLX model)│
           │                       └──────────────────────────┘
           │                                  │
           │                                  ▼
           │                       ┌──────────────────────────┐
           │                       │ Feat-0002                  │
           │                       │ document-indexing           │
           │                       │ (Chroma + in-mem BM25 +     │
           │                       │  PII entity index)          │
           │                       └──────────┬────────────────┘
           │                                  │
           ▼                                  ▼
┌─────────────────────────┐     ┌──────────────────────────┐
│ Feat-0008                │◀───▶│ Feat-0005                 │
│ storage-persistence        │     │ semantic-search-qa         │
│ (S3 + SQLite/SQLAlchemy)   │     │ (RBAC filter → mask →      │
└──────────┬────────────────┘     │  Claude answer generation) │
           │                       └──────────┬────────────────┘
           │                                  │
           └──────────────┬───────────────────┘
                           ▼
              ┌──────────────────────────┐
              │ Feat-0007                 │
              │ security-access-control    │
              │ (auth, RBAC, masking,      │
              │  audit, encryption, LLM    │
              │  guardrails)               │
              └──────────────────────────┘
```

## Tech Stack Per Layer

| Layer | Stack |
|---|---|
| UI ([[Features/Feat-0006-streamlit-ui/Index.md]]) | Streamlit — no React/TS, no separate frontend build |
| API ([[Features/Feat-0003-document-ingestion/Index.md]], [[Features/Feat-0001-ade-extraction-service/Index.md]]) | FastAPI (two independent apps, two ports) |
| Async processing ([[Features/Feat-0004-pipeline-workers/Index.md]]) | Python `threading` + in-process `queue.Queue` — no message broker (SQS/Kafka/RabbitMQ) |
| Vector search | ChromaDB (`PersistentClient`, local disk) |
| Keyword search | Custom in-memory BM25 (`rank-bm25`), despite the module being named `opensearch_index.py` — there is no real OpenSearch cluster |
| Embeddings | `sentence-transformers` (`all-MiniLM-L6-v2` default) |
| Reranking | Cross-encoder (`ms-marco-MiniLM-L-6-v2`) |
| LLM (answer generation) | Anthropic Claude, via the `anthropic` SDK |
| LLM (clinical extraction) | Local Qwen2.5-7B + QLoRA adapter, MLX quantized inference (Apple Silicon, no CUDA) |
| Relational storage | SQLite via SQLAlchemy ORM — no migration tool (Alembic), schema created via `Base.metadata.create_all()` |
| Blob storage | AWS S3, KMS or SSE-S3 encrypted |
| Tracing (optional) | LangSmith, enabled only if `LANGSMITH_API_KEY` is set (`monitoring/tracing.py`) |

## Cross-Cutting Architectural Decisions

These recur across 2+ features — see each feature's own "Architectural Decisions" table for
single-feature choices.

| Decision | Reason | Scope |
|---|---|---|
| **No cryptographic identity verification anywhere in the FastAPI layer** — role is a self-asserted HTTP header or Python kwarg, checked only in application code | Prototype-stage; the only real authentication boundary in the whole system is the Streamlit session login | [[Features/Feat-0003-document-ingestion/Index.md]], [[Features/Feat-0001-ade-extraction-service/Index.md]], [[Features/Feat-0007-security-access-control/Index.md]] — see `.claude/rules/security.md`'s Project Auth Model for the full citation trail |
| **In-process communication over HTTP wherever possible** — the UI calls backend Python functions directly rather than making HTTP requests to the FastAPI apps | Single-deployment-unit simplicity; avoids a network hop and a second auth boundary between UI and backend logic | [[Features/Feat-0006-streamlit-ui/Index.md]] → every backend feature it consumes |
| **In-process queues instead of a message broker** for the async pipeline | Simplicity for a single-process deployment | [[Features/Feat-0004-pipeline-workers/Index.md]] — trades away durability across restarts; only partially mitigated by `run.py::recover_stuck_docs()` |
| **No database migration tool** — SQLAlchemy models plus `create_all()` only | Prototype speed; schema hasn't needed to evolve yet | [[Features/Feat-0008-storage-persistence/Index.md]] — will need a real migration story before the schema can safely change post-deployment |
| **Fail-safe (deny-by-default) RBAC/masking** — an unrecognized role or missing metadata masks/blocks rather than defaulting open | PHI safety over convenience | [[Features/Feat-0007-security-access-control/Index.md]], [[Features/Feat-0002-document-indexing/Index.md]] |
| **Graceful degradation over hard failure** in the async pipeline and in answer generation — a failed ADE extraction, a failed vector search, or a missing API key all produce a partial result or an in-band message rather than an exception | Keep the pipeline/UI usable even when one dependency is degraded | [[Features/Feat-0004-pipeline-workers/Index.md]], [[Features/Feat-0005-semantic-search-qa/Index.md]], [[Features/Feat-0006-streamlit-ui/Index.md]] |

## Coupling Graph (from frontmatter `depends_on`/`consumed_by`)

```
Feat-0001-ade-extraction-service    ← consumed_by ── Feat-0004-pipeline-workers

Feat-0002-document-indexing         ← consumed_by ── Feat-0004-pipeline-workers
                                     ← consumed_by ── Feat-0005-semantic-search-qa

Feat-0003-document-ingestion        ── depends_on ──→ Feat-0007-security-access-control
                                     ── depends_on ──→ Feat-0008-storage-persistence
                                     ← consumed_by ── Feat-0004-pipeline-workers
                                     ← consumed_by ── Feat-0006-streamlit-ui

Feat-0004-pipeline-workers          ── depends_on ──→ Feat-0003-document-ingestion
                                     ── depends_on ──→ Feat-0002-document-indexing
                                     ── depends_on ──→ Feat-0007-security-access-control
                                     ── depends_on ──→ Feat-0008-storage-persistence
                                     ── depends_on ──→ Feat-0001-ade-extraction-service
                                     ← consumed_by ── Feat-0006-streamlit-ui

Feat-0005-semantic-search-qa        ── depends_on ──→ Feat-0002-document-indexing
                                     ── depends_on ──→ Feat-0007-security-access-control
                                     ← consumed_by ── Feat-0006-streamlit-ui

Feat-0006-streamlit-ui              ── depends_on ──→ (everything above except Feat-0001, which it never calls directly)

Feat-0007-security-access-control   ← consumed_by ── Feat-0003, Feat-0004, Feat-0005, Feat-0006
                                     (no outgoing dependencies — the base of the graph)

Feat-0008-storage-persistence       ← consumed_by ── Feat-0003, Feat-0004, Feat-0006, Feat-0007
                                     (no outgoing dependencies — the base of the graph)
```

**Highest-risk couplings** (compile-time imports, per the dependency-mapper pass):
- [[Features/Feat-0004-pipeline-workers/Index.md]] imports directly from [[Features/Feat-0003-document-ingestion/Index.md]]'s `ingestion.{parsers,ocr,registry,state_machine,metadata,pii}` — a type change in the registry or state machine breaks multiple workers at once.
- [[Features/Feat-0004-pipeline-workers/Index.md]]'s `ExtractionWorker` fans out to both `EmbeddingWorker` and `KeywordIndexWorker` via the same queue message shape — a payload change breaks both consumers simultaneously, with nothing at build time to catch it (runtime-only coupling, same risk profile as an event pub/sub pair).
- Every backend feature imports [[Features/Feat-0007-security-access-control/Index.md]] and [[Features/Feat-0008-storage-persistence/Index.md]] directly (no facade/interface layer) — both are effectively unversioned shared libraries with 4+ internal consumers each.

## Not Modeled as Features

These exist in the repo but are dev/ops tooling rather than product features, and are intentionally
not given their own `Feat-NNNN` page:

- `evaluation/run_eval.py` — offline retrieval-quality evaluation (Hit@K, MRR, Precision) against [[Features/Feat-0002-document-indexing/Index.md]], via LangSmith
- `monitoring/tracing.py` — optional LangSmith tracing setup, called from `run.py` and `streamlit_app.py`
- `AiHarness/` — this repository's own AI-assisted-development harness (skills, eval cases, spec templates) for building *this* codebase — not part of the shipped product
- `Dataset/`, `Typed/` — sample medical-record PDF fixtures for testing/demos, not code
- `mlx_adapter/` — model artifacts (QLoRA adapter weights + config) consumed by [[Features/Feat-0001-ade-extraction-service/Index.md]], not code
- `scripts/` (repo-root) — operational scripts (`convert_to_mlx.py`, `reset_stores.py`, `seed_mock_records.py`, `start_workers.py`) for local dev/ops, not a product feature
