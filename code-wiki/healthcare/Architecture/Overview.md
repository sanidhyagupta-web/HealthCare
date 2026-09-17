# Architecture Overview

## System Topology

A single-process Python monolith, not a microservice architecture — with one exception
([[Feat-0004-llm]]'s `ade_api.py`, a second FastAPI process for local MLX inference). There is no
separate frontend service: [[Feat-0008-ui]] is a Streamlit app that imports every backend module
directly and calls it in-process. The only real network boundaries in the whole system are:

1. `POST /ingest/bulk` on the [[Feat-0001-app]] FastAPI app (unauthenticated beyond a self-asserted role header)
2. `POST /extract` / `GET /health` on `llm/ade_api.py` (no authentication at all)
3. Outbound HTTPS to AWS S3/KMS and the Anthropic API

```
                         ┌─────────────────────────┐
                         │   ui/  (Streamlit, FE)   │
                         └────────────┬─────────────┘
              in-process imports, no HTTP client layer
        ┌──────────┬──────────┬───────┴──────┬───────────┬─────────────┐
        ▼          ▼          ▼              ▼           ▼             ▼
   Feat-0001   Feat-0006   Feat-0002     Feat-0004    Feat-0007    Feat-0003
     app        security    indexing        llm        workers      ingestion
        │          │            │        (HTTP to        │             │
        │          │            │       ade_api:8001)     │             │
        └────┬─────┴─────┬──────┴──────────────┬──────────┴──────┬──────┘
             ▼            ▼                     ▼                 ▼
                    Feat-0009 platform (S3, SQLite, tracing)
                                     ▲
                               everyone reads
                              app.config.Settings
```

`Feat-0005-search` (`search/pipeline.py`) is drawn separately below — it is not in this main graph
because, per its own page, nothing in the live application currently calls it.

## Tech Stack Per Layer

| Layer | Stack |
|---|---|
| API | FastAPI (`app/main.py`), `uvicorn` |
| UI | Streamlit (single process, no separate build/bundler) |
| Async pipeline | stdlib `threading` + `Queue.Queue`, no external broker |
| Vector store | ChromaDB (local persistent) |
| Keyword search | `rank-bm25`, JSON-persisted |
| Embeddings / reranking | `sentence-transformers` |
| SQL persistence | SQLAlchemy declarative models, SQLite, **no migration tool** |
| Object storage | AWS S3 with KMS encryption |
| LLM (answer generation) | Anthropic Claude API |
| LLM (structured extraction) | local MLX inference (`mlx-lm`, Apple-silicon), separate FastAPI process |
| PII detection | Presidio, with a regex fallback if unavailable |

## Cross-Cutting Architectural Decisions

These recur across two or more features — a single feature's own decision belongs on that feature's
page instead.

| Decision | Reason | Recurs In |
|---|---|---|
| `app/config.py:Settings` is one dataclass instance every module imports directly | Single environment-driven config surface, no DI container | [[Feat-0001-app]] (owner), [[Feat-0002-indexing]], [[Feat-0003-ingestion]], [[Feat-0004-llm]], [[Feat-0006-security]], [[Feat-0007-workers]], [[Feat-0009-platform]] |
| RBAC role lists live in exactly one file (`ingestion/metadata/rbac_policy.py`) | Prevent ingest-time tagging and query-time enforcement from drifting apart | [[Feat-0003-ingestion]] (owner), [[Feat-0006-security]], [[Feat-0005-search]], [[Feat-0008-ui]] |
| Filter-then-mask is meant to be a single non-negotiable call order before any chunk reaches an LLM | Prevent PII from reaching a model that shouldn't see it | [[Feat-0005-search]] (defines it), [[Feat-0006-security]], [[Feat-0003-ingestion]] — **currently not followed on the live path, see below** |
| No message-schema validation between async pipeline stages | Simplicity — the pipeline was built incrementally, one worker per stage | [[Feat-0007-workers]], [[Feat-0003-ingestion]] |
| Self-asserted role, not verified identity, gates every access-control decision in the system | No auth infrastructure (JWT/session tokens/SSO) exists yet — this is a prototype | [[Feat-0001-app]], [[Feat-0003-ingestion]], [[Feat-0006-security]], [[Feat-0008-ui]] |

## System-Wide Findings Worth Flagging Up Front

These surfaced independently from more than one scan pass and are severe enough to summarize here
rather than leave buried in one feature page:

1. **The documented filter→mask→generate order is not enforced on the live query path.**
   [[Feat-0005-search]]'s `secure_results()` implements it correctly but is called only from a test.
   The real path, `ui/search_page.py` ([[Feat-0008-ui]]), calls the RBAC filter but skips the PII
   mask before the LLM call. `evaluation/run_eval.py` has the same gap. See Feat-0005-search's
   "Human Escalation Required" section.
2. **No endpoint in this system verifies caller identity.** `POST /ingest/bulk` and `POST /extract`
   both trust self-asserted headers/no auth at all. See `.claude/rules/security.md` and
   [[Feat-0001-app]]/[[Feat-0004-llm]].
3. **`ui/audit_page.py` has no role gate** — every authenticated user, including `researcher` and
   `billing`, can read every other user's search queries and document-access history. See
   [[Feat-0006-security]] BR-04.
4. **There is no migration tool anywhere in this repo.** Schema exists only as SQLAlchemy declarative
   models, created via `create_all()`. See `Schemas/schemas.md`.

## Coupling Graph (from frontmatter `depends_on`/`consumed_by`)

| Feature | depends_on | consumed_by |
|---|---|---|
| Feat-0001-app | ingestion, security, platform, workers | ui, ingestion, security, indexing, llm, platform, workers |
| Feat-0002-indexing | platform | ui, workers |
| Feat-0003-ingestion | platform, app | ui, app, workers, search |
| Feat-0004-llm | platform | ui, workers |
| Feat-0005-search | security, ingestion | *(none — see its own page)* |
| Feat-0006-security | platform, app | ui, app, workers, search |
| Feat-0007-workers | ingestion, platform, indexing, security, llm | ui, app |
| Feat-0008-ui | app, platform, ingestion, indexing, security, llm, workers | *(none — top of the stack)* |
| Feat-0009-platform | app | app, ingestion, indexing, llm, security, workers, ui |

Note the `app ⇄ ingestion`/`app ⇄ platform`/`app ⇄ security` edges run in both directions: `app`
depends on those modules for endpoint logic, while they in turn import `app.config` for settings.
This is a hub-and-spoke config dependency, not a layering violation — see the "Settings" decision
above — but it means `app/config.py` cannot be changed without checking nearly every feature in this
repo.

## High-Risk Couplings (from the dependency-mapper's repo-wide scan)

- **[[Feat-0007-workers]] ↔ [[Feat-0003-ingestion]] (compile-time, many imports)** — parsing/OCR/chunking/PII logic changes break workers at build time.
- **[[Feat-0007-workers]] → [[Feat-0002-indexing]] (compile-time, 3 workers)** — an index-schema change breaks `PiiWorker`, `EmbeddingWorker`, and `KeywordIndexWorker` simultaneously.
- **[[Feat-0007-workers]] → [[Feat-0004-llm]] (runtime HTTP, no compile-time protection)** — `ade_api.py`'s response shape (`drug`, `adverse_effect`) can change and break `ExtractionWorker` silently, with no build-time signal.
- **[[Feat-0008-ui]] → [[Feat-0006-security]] / [[Feat-0003-ingestion]] (compile-time)** — RBAC policy or security-API shape changes force UI updates.

## Excluded From This Scan

Not documented as features because they are development tooling, sample data, or model artifacts
rather than product code:

- `AiHarness/` — a separate coding-harness/eval-prompt system for driving AI coding tools against this repo; not part of the running application.
- `Dataset/`, `Typed/` (top-level), `scripts/Typed/` — sample healthcare documents used for local testing/seeding.
- `mlx_adapter/` — model adapter config/weights, consumed by [[Feat-0004-llm]] but not itself application logic.
- `evaluation/` — a retrieval-quality eval harness (`run_eval.py`); it exercises the same query path as [[Feat-0008-ui]] and reportedly has the same masking gap noted above, but is a dev tool, not a served feature.

*Open question: should `evaluation/run_eval.py` be documented as its own feature page given it
duplicates production query-path logic and inherits the same PII-masking gap? It was excluded here
as a dev/CI tool, not a served feature, but a future scan could reconsider this.*
