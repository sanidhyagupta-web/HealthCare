# Harmony — AI Harness

## Architecture Overview

Harmony is a HIPAA-aware healthcare semantic search system. Documents enter through a 6-stage ingestion pipeline (parse → markdown → chunk → PII-redact → embed → index), each stage run by a daemon-thread worker consuming an in-process `queue.Queue`. Processed chunks land in ChromaDB (vector) and a BM25 index (keyword). At query time, both stores are retrieved, merged with RRF, reranked by a cross-encoder, and answered by Claude with grounded citations. Every retrieval event is audit-logged. PII redaction happens at ingest (Presidio → `[TYPE]` placeholders); role-based masking is applied again at query time based on the caller's role.

## Architecture Diagram

```text
INGESTION
Streamlit Upload
  -> S3 + KMS encrypted raw document
  -> Document validation
  -> Parsing queue
  -> Parser/OCR worker
      -> typed PDF: PyMuPDF
      -> scanned PDF: OCR/Textract/Tesseract/Qwen Vision fallback
  -> Markdown queue
  -> Markdown converter
  -> S3 + KMS encrypted markdown
  -> Chunking queue
  -> Entity-preserving parent-child chunking
  -> Medical spell checker
  -> PII detection
  -> KMS-encrypted redacted chunks
  -> Metadata + RBAC policy attachment
  -> Embedding queue + keyword queue
  -> Vector store + keyword index

SEARCH
Streamlit Query
  -> Rate limiter
  -> RBAC + authentication
  -> Prompt/security guardrails
  -> System prompt construction
  -> Query PII detection
  -> Candidate filtering by redacted PII hash + allowed roles
  -> Vector retrieval + BM25 retrieval
  -> RRF merge
  -> Cross-encoder rerank
  -> LLM answer with citations
  -> Output PII/HIPAA validation
  -> Audit log
  -> Response
```

## How to Discover New Concepts

Before implementing any feature, inspect `/skills`. Choose the most relevant skill files and follow them exactly. If a feature touches ingestion, search, security, compliance, RBAC, PII, embeddings, chunking, or validation, there is probably a skill for it.

## New Feature Workflow

For every new feature:

1. Create `/features/active/<feature-name>/`.
2. Copy these templates into that folder:
   - `/templates/01-product-spec-template.md`
   - `/templates/02-technical-spec-template.md`
   - `/templates/03-implementation-plan-template.md`
3. Fill the copied templates using the current codebase and the relevant skills.
4. Only then implement the feature.
5. Add or update an eval case under `/evals` if the feature represents a repeatable pattern.

## Folder Structure for New Features

```text
features/active/<feature-name>/
  01-product-spec.md
  02-technical-spec.md
  03-implementation-plan.md
  notes.md
```

Implementation should map to the existing app structure. If the repo does not yet have these folders, create them consistently:

```text
src/
  ingestion/
  parsing/
  chunking/
  pii/
  embeddings/
  retrieval/
  reranking/
  audit/
  auth/
  api/
  ui/
  common/
tests/
  unit/
  integration/
  eval/
```

## Pointer to Templates

When asked to build a new feature, follow the sequence in `/templates`. Never jump directly to code unless the user explicitly asks for a quick spike. Even for spikes, document assumptions in the feature folder.

## Skill Glossary

- `document-ingestion.md`: Validating, encrypting, parsing, and registering uploaded medical documents.
- `chunking-strategy.md`: Medical parent-child chunking rules and hash-based duplicate checks.
- `embedding-generation.md`: Embedding model usage, batching, retry behavior, and vector storage.
- `hybrid-search.md`: Vector + keyword retrieval, RRF merge, and reranking.
- `audit-logging.md`: Required audit events for ingestion, search, access, and result viewing.
- `pii-masking.md`: PII detection, redaction, role-aware masking, and output validation.
- `access-control.md`: RBAC, per-document permissions, allowed roles, and treating-team checks.
- `llm-response-validation.md`: Grounded answers, citations, hallucination handling, and no-answer behavior.
- `security-guardrails.md`: Prompt injection, secret exposure, unsafe request, and system prompt rules.
- `observability.md`: LangSmith traces, metrics, latency benchmarks, and error tracking.

## Non-Negotiable Rules

- Never hardcode credentials, API keys, KMS keys, database URLs, or patient identifiers.
- Never create fake API data to make tests pass.
- Never bypass RBAC, audit logging, PII masking, or output validation.
- Never return unredacted PII to non-treating staff.
- Never answer from the LLM without retrieved citations.
- Never index raw unredacted chunks into a searchable store.
- Never silently swallow OCR, parsing, embedding, or indexing failures.
- Never mix synthetic demo records with real patient records.
- Never log raw clinical text, raw PII, or secrets.
- Never use global mutable state for user identity, role, permissions, or patient scope.

## Repo-Specific Architectural Rules

- Every uploaded document must be validated before parsing.
- Every stored document artifact must be encrypted at rest using KMS or local equivalent.
- Every document must have a registry entry with document ID, source file, status, retry count, and timestamps.
- Every chunk must preserve parent-child hierarchy and source metadata.
- Every chunk must include metadata: `patient_id`, `source_file`, `source_page`, `chunk_id`, `source_section`, `allowed_roles`, and RBAC policy fields.
- Every retrieval must pass through audit logging.
- Every search must combine vector and keyword retrieval unless explicitly documented as a diagnostic mode.
- Every final result must include source citations.
- Every query must be logged with user identity, timestamp, query text/hash, role, result IDs, and decision status.
- Search must filter by access control before results are shown.
- Search must validate final LLM output for PII masking and citation grounding.
- Ingestion statuses must be explicit: `VALIDATED`, `PARSED`, `MARKDOWN_READY`, `CHUNKED`, `PII_PROCESSED`, `INDEXED`, `FAILED`.
- Retryable jobs must increment `retry_count` and persist failure reason.

## Technology Stack (authoritative)

| Concern | Choice |
|---|---|
| Embedding model | `all-MiniLM-L6-v2` (SentenceTransformer, 384-dim, batch 32) |
| Reranker | `cross-encoder/ms-marco-MiniLM-L-6-v2` |
| Vector store | ChromaDB (`data/chroma/`) |
| Keyword index | `rank_bm25` BM25Okapi → `data/bm25_index.json` |
| LLM | Claude via `llm/claude_client.py` |
| PII detection | Microsoft Presidio + regex fallback |
| Encryption | AWS KMS (cloud) / local envelope key (`app/config.py`) |
| OCR | Tesseract → Qwen Vision fallback (no Textract dependency) |
| Pipeline orchestration | 6 daemon-thread workers + `queue.Queue` — no LangChain/LangGraph |
| Observability | LangSmith traces |

## Definition of Done

A feature is complete only when:

1. Product spec, technical spec, and implementation plan exist.
2. Relevant skills were followed.
3. Unit tests and at least one integration test were added.
4. Audit logging, RBAC, PII masking, and citations were considered.
5. Evals were added or updated when the feature changes agent behavior.
6. The feature can be run from a fresh checkout using documented commands.
