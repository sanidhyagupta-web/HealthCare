# Architecture Overview — HealthCare

Last updated: 2026-09-17

## System Topology

A single Python repository, no submodules or separate frontend/backend services — one
process tree, several entry points:

```
                    ┌─────────────────────────┐
  Streamlit UI  ───▶ │  ui/ (Feat-0006)         │──▶ calls everything below directly,
  (port 8501,        │  streamlit_app.py + 5    │    in-process (Python function calls,
   browser)          │  pages                   │    NOT HTTP, except where noted)
                    └───────────┬─────────────┘
                                │
        ┌───────────────────────┼───────────────────────────┐
        ▼                       ▼                           ▼
┌───────────────┐      ┌────────────────────┐      ┌──────────────────────┐
│ Feat-0002       │      │ Feat-0004            │      │ Feat-0005              │
│ Document        │      │ Security & Access    │      │ Semantic Search &      │
│ Ingestion       │◀────▶│ Control              │◀────▶│ Indexing               │
│ Pipeline        │      │ (auth, RBAC, audit,  │      │ (Chroma, BM25,         │
│ (app/, storage/)│      │  encryption,         │      │  reranker)             │
│                 │      │  guardrails)         │      │                        │
└───────┬─────────┘      └──────────┬───────────┘      └───────────┬────────────┘
        │ enqueues                  │ enforced by                 │ enforced by
        ▼                           │ Feat-0001, Feat-0006         │ Feat-0006's
┌───────────────────┐               │                              │ search flow
│ Feat-0001           │◀─────────────┘                              │
│ Async Processing    │──────────── writes to ─────────────────────▶│
│ Workers             │
│ (workers/, queues/) │──── HTTP :8001 ────▶┌─────────────────────┐
└─────────┬───────────┘                     │ Feat-0003             │
          │                                  │ LLM Extraction /      │
          ▼                                  │ Inference             │
┌───────────────────┐                        │ (ADE MLX server +    │
│ Feat-0007           │◀── all of the above ──│  Claude API client)  │
│ Platform Data Layer │    read/write through  └───────────────────────┘
│ (db/, monitoring/)  │    db.get_db()
└─────────────────────┘
```

**External services**: AWS S3 (raw file storage, KMS-encrypted), a local MLX-quantized
Qwen2.5-7B server on `localhost:8001` (drug/ADE extraction), Anthropic's Claude API
(cited RAG answers), and optionally a third-party spell-check API (Sapling, used only as an
OCR-quality fallback).

## Tech Stack Per Layer

| Layer | Stack |
|---|---|
| UI | Streamlit (server-rendered Python, not a JS SPA) |
| HTTP API (bulk ingest) | FastAPI, `app/main.py` |
| Async processing | Python `threading` + in-memory `queue.Queue`-based pipeline (no external broker — no Kafka/SQS/RabbitMQ) |
| Persistence | SQLite via SQLAlchemy, no migration framework |
| Vector search | ChromaDB |
| Keyword search | `rank_bm25`, in-memory + JSON-persisted |
| LLM | Local MLX-quantized model (extraction) + Anthropic Claude API (RAG answers) |
| Object storage | AWS S3 (KMS-encrypted) |
| PII detection | Microsoft Presidio, with a regex fallback if unavailable |

## Cross-Cutting Architectural Decisions

These recur across two or more features — a single feature's own decision belongs in that
feature's own file, not here.

| Decision | Reason | Applies To |
|---|---|---|
| In-memory Python queues, not a message broker | Simplicity for a single-process deployment; explicitly not durable across a process restart — `run.py:recover_stuck_docs()` exists specifically to compensate for this | Feat-0001, Feat-0002 |
| Query-time enforcement order: RBAC filter, then PII mask, never the reverse | A chunk that fails RBAC must never reach the masking step and be returned anyway | Feat-0004, Feat-0005, Feat-0006 |
| No foreign keys enforced at the database level; all cross-table references are application-maintained | SQLite + SQLAlchemy declarative models, added incrementally without a migration tool | Feat-0002, Feat-0004, Feat-0005, Feat-0007 |
| Two independent entry points (Streamlit session auth, FastAPI header-trust) with no shared session | The Streamlit UI and the FastAPI bulk-ingest endpoint were built as separate surfaces; they were never unified under one auth mechanism | Feat-0002, Feat-0004, Feat-0006 |

## Known System-Wide Gaps

Carried up from the per-feature scans because they cross feature boundaries:

- **`POST /ingest/bulk` trusts an unauthenticated `role` HTTP header.** This is the single
  highest-severity finding across the whole scan — see Feat-0002's and Feat-0004's Access
  Control sections. Any caller can claim `role: admin`.
- **`search/pipeline.py`'s `secure_results()` orchestrator is not actually called** by
  `ui/search_page.py`, the only real caller — the UI reimplements the RBAC-filter-then-mask
  sequence itself instead. See Feat-0005's Access Control section.
- **`monitoring/tracing.py` (LangSmith) is entirely unused** and would raise `AttributeError`
  if it were ever called, because `app/config.py` doesn't define the settings it reads. See
  Feat-0007.
- **No database migration framework.** Schema changes to `db/models.py` are unversioned.

## Coupling Graph (from Features/*/Index.md frontmatter)

| Feature | depends_on | consumed_by |
|---|---|---|
| Feat-0001 Async Processing Workers | Feat-0002, Feat-0003, Feat-0004, Feat-0005, Feat-0007 | Feat-0002, Feat-0006 |
| Feat-0002 Document Ingestion Pipeline | Feat-0001, Feat-0004, Feat-0007 | Feat-0001, Feat-0005, Feat-0006 |
| Feat-0003 LLM Extraction / Inference | *(none)* | Feat-0001, Feat-0006 |
| Feat-0004 Security & Access Control | Feat-0002, Feat-0007 | Feat-0001, Feat-0002, Feat-0005, Feat-0006 |
| Feat-0005 Semantic Search & Indexing | Feat-0002, Feat-0004 | Feat-0001, Feat-0006 |
| Feat-0006 Healthcare Search & Upload UI | Feat-0001, Feat-0002, Feat-0003, Feat-0004, Feat-0005, Feat-0007 | *(none)* |
| Feat-0007 Platform Data Layer | *(none)* | Feat-0001, Feat-0002, Feat-0004, Feat-0006 |

Note the mutual `Feat-0001 ↔ Feat-0002` edge: Feat-0002 enqueues into queues that Feat-0001's
workers own, and Feat-0001's workers import Feat-0002's registry/state-machine/validator
modules directly. This is the tightest, highest-risk coupling in the system — a change to
either side's contract (queue message shape, state machine transitions) breaks the other at
runtime with no compile-time signal, since Python doesn't check this at import time beyond
name resolution.

## Excluded From This Wiki

Not scanned as features — fixtures, tooling, or content unrelated to the running application:
`Dataset/`, `Typed/`, `data/` (sample documents and PII indexes), `AiHarness/` (this project's
own AI-agent evaluation harness), `evaluation/` (a standalone eval script), `scripts/` (ops
utilities: `seed_mock_records.py`, `reset_stores.py`, `start_workers.py` — `convert_to_mlx.py`
is the one exception, covered under Feat-0003 since it produces that feature's model adapter).
