# Architecture Overview — HealthCare

## System Topology

A single Python repository, no JS/TS anywhere. Two runtime processes:

1. **Main application process** — FastAPI ingestion API (`app/main.py`) + background worker
   threads (`workers/`, started by `run.py`) + the Streamlit UI (`ui/`), all sharing the same
   in-process Python objects (in-memory queues, a shared SQLite DB via SQLAlchemy). There is no
   HTTP boundary between the UI and the ingestion/search backend — they are direct function calls
   in the same process space.
2. **LLM / ADE Extraction Service** ([Feat-0002](../Features/Feat-0002-llm-ade-extraction-service/Index.md)) —
   a separate `uvicorn` process on port 8001 (`llm/ade_api.py`), the only cross-process HTTP
   boundary in the system. Called once per sentence by `workers/extraction_worker.py` with a 30s
   timeout and no authentication.

```
                        ┌─────────────────────────────────────────────┐
                        │              Main process                  │
  ┌──────────┐  in-proc │  ┌────────────┐   in-mem    ┌────────────┐  │   HTTP, no auth   ┌──────────────┐
  │  ui/     │◄────────►│  │ app/main.py│◄───queues──►│  workers/  │  │───────────────────►│ llm/ade_api  │
  │ Streamlit│  calls   │  │ (FastAPI)  │             │ (7 stages) │  │  (port 8001)       │ (Feat-0002)  │
  └────┬─────┘          │  └────────────┘             └─────┬──────┘  │                    └──────────────┘
       │                │                                    │        │
       │  in-proc calls │  ┌────────────┐   ┌────────────┐  ▼        │
       └───────────────►│  │ search/    │   │ security/  │◄──────────┤
                        │  │ indexing/  │◄─►│ (Feat-0005)│            │
                        │  │ (Feat-0003)│   └────────────┘            │
                        │  └────────────┘                             │
                        │        ▲                                    │
                        │        └──── db/ (SQLite, shared) ──────────┤
                        └─────────────────────────────────────────────┘
```

## Tech Stack Per Layer

| Layer | Stack |
|---|---|
| Ingestion API | FastAPI, `python-multipart`, `uvicorn` |
| Background processing | Plain Python threads + in-memory `queue.Queue`-style queues (`queues/`), no external broker (no SQS/Kafka/Redis) |
| Parsing/OCR | `pymupdf` (typed PDFs), `pytesseract`+`pdf2image` (scanned PDFs), custom DICOM handling |
| PII detection | `presidio-analyzer`/`presidio-anonymizer`, with a regex fallback if unavailable |
| Chunking | Custom entity-preserving chunker (`ingestion/chunking/`) |
| Encryption | `cryptography` (Fernet) |
| Vector search | `chromadb` + `sentence-transformers` embeddings |
| Keyword search | `rank-bm25`, persisted to a JSON file (module named `opensearch_index.py` despite not using OpenSearch) |
| Reranking | Cross-encoder via `sentence-transformers` |
| Answer generation (search) | Anthropic Claude API (`llm/claude_client.py`) |
| ADE extraction (separate service) | Local Qwen2.5-7B, 4-bit quantized via `mlx-lm`, QLoRA adapter, Apple Silicon only |
| Persistence | SQLite via SQLAlchemy, no migrations tool (`Base.metadata.create_all()`) |
| Object storage | AWS S3 with KMS encryption (`boto3`) |
| Frontend | Streamlit (Python) — no JS/React anywhere in this repo |
| Testing | `pytest` + `pytest-cov`; no linter/formatter/type-checker configured |

## Cross-Cutting Architectural Decisions

- **No message broker.** All pipeline stages communicate through in-memory Python queues
  (`queues/`), not SQS/Kafka/RabbitMQ. This means queue state does not survive a process restart —
  `run.py:recover_stuck_docs()` is the compensating mechanism, and it only covers two of the seven
  possible in-flight statuses (see [Feat-0001](../Features/Feat-0001-document-ingestion-pipeline/Index.md)'s
  open question).
- **RBAC as the single access-control model, everywhere** — one `role` string, checked against
  either a static allow-list (`ingestion/metadata/rbac_policy.py`) or per-chunk `allowed_roles`
  metadata (`security/access_control.py`). There is no ownership-based or scope/token-based access
  control anywhere in the repo.
- **Two independent implementations of "secure retrieval" exist and have diverged** — 
  `search/pipeline.py:secure_results()` (filter + mask) is the documented flow, but
  `ui/search_page.py` (the only thing actually called by a user) implements only the filter half.
  See [Feat-0003](../Features/Feat-0003-search-retrieval/Index.md) BR-06. This is the single
  highest-priority finding from this scan.
- **Authentication is real for humans, absent for the one machine-to-machine endpoint.** The
  Streamlit UI performs genuine login; the FastAPI `POST /ingest/bulk` endpoint trusts a
  client-supplied `role` header with no identity verification at all. See
  [Feat-0005](../Features/Feat-0005-security-access-control/Index.md) BR-06 and
  `.claude/rules/security.md`.
- **PHI encryption fails open, not closed.** If the encryption library or key is unavailable,
  `security/encryption.py` logs an ERROR and returns plaintext rather than refusing the operation.

## Coupling Graph (from Features frontmatter)

```
Feat-0004 (Healthcare Semantic Search UI, frontend)
  ├─ depends_on → Feat-0001 (Document Ingestion Pipeline)
  ├─ depends_on → Feat-0003 (Search & Retrieval)
  └─ depends_on → Feat-0005 (Security & Access Control)

Feat-0001 (Document Ingestion Pipeline)
  ├─ depends_on → Feat-0005 (Security & Access Control)
  └─ depends_on → Feat-0002 (LLM / ADE Extraction Service)   [HTTP, cross-process]

Feat-0003 (Search & Retrieval)
  ├─ depends_on → Feat-0005 (Security & Access Control)
  └─ depends_on → Feat-0001 (Document Ingestion Pipeline)    [reads chunk/document registries]

Feat-0002 (LLM / ADE Extraction Service)
  └─ (no repo-internal dependencies — standalone service)

Feat-0005 (Security & Access Control)
  └─ (no repo-internal dependencies — leaf shared-library)
```

Highest-risk edge: **Feat-0001 → Feat-0002 is the only cross-process, HTTP, unauthenticated
coupling in the system** (`workers/extraction_worker.py` → `POST http://localhost:8001/extract`).
Every other edge is an in-process Python import/call, so a breaking change is at least visible at
import time; this one is not.

## Open Questions Carried From Feature Scans

See each feature's own Index.md for full context — listed here so they're visible without opening
every file:

- Feat-0001: should `recover_stuck_docs()` cover more in-flight statuses? Is `monitoring/tracing.py`
  referencing settings fields that don't exist in `app/config.py` dead code or a real bug?
- Feat-0002: is `/extract` ever reachable from outside localhost? Is `GET /health` consumed by
  anything?
- Feat-0003 / Feat-0005: is the missing `apply_role_mask()` call in `ui/search_page.py` a known
  gap or an oversight? Is `/ingest/bulk`'s unauthenticated role header an accepted network-boundary
  decision or a real vulnerability? Should the audit trail be role-gated?
- Feat-0004: which of `secure_results()` or `ui/search_page.py`'s inline flow is meant to be the
  long-term pattern?
