<!-- GENERATED — regenerated from each Feat-NNNN-*/Index.md's frontmatter. Do not hand-edit;
     fix the source frontmatter instead and regenerate. -->

# Features Index

## Feature Catalog

### backend-service

| feat_id | feature | domain | criticality | path |
|---|---|---|---|---|
| Feat-0001 | ade-extraction-service | clinical-nlp | low | `Feat-0001-ade-extraction-service/Index.md` |
| Feat-0002 | document-indexing | retrieval | high | `Feat-0002-document-indexing/Index.md` |
| Feat-0003 | document-ingestion | document-intake | high | `Feat-0003-document-ingestion/Index.md` |
| Feat-0004 | pipeline-workers | document-processing | high | `Feat-0004-pipeline-workers/Index.md` |
| Feat-0005 | semantic-search-qa | retrieval-qa | high | `Feat-0005-semantic-search-qa/Index.md` |

### frontend-feature

| feat_id | feature | domain | criticality | path |
|---|---|---|---|---|
| Feat-0006 | streamlit-ui | user-interface | high | `Feat-0006-streamlit-ui/Index.md` |

### shared-library

| feat_id | feature | domain | criticality | path |
|---|---|---|---|---|
| Feat-0007 | security-access-control | security | high | `Feat-0007-security-access-control/Index.md` |
| Feat-0008 | storage-persistence | persistence | high | `Feat-0008-storage-persistence/Index.md` |

## Workflow Routing Rules

Keyword → feature file, so a consumer loads only what it needs instead of the whole tree.

| Keyword / Area | Feature File |
|---|---|
| login, session, auth, password | Feat-0007-security-access-control |
| RBAC, role, department, allowed_roles, masking, PII | Feat-0007-security-access-control (policy tables), Feat-0002-document-indexing (metadata contract), Feat-0005-semantic-search-qa (enforcement order) |
| upload, ingest, validation, bulk ingest, `/ingest/bulk` | Feat-0003-document-ingestion |
| OCR, parsing, markdown conversion, chunking, worker, queue, DLQ | Feat-0004-pipeline-workers |
| embedding, vector search, Chroma, BM25, keyword search, reranker | Feat-0002-document-indexing |
| search UI, Q&A, Claude, citations, `generate_answer` | Feat-0005-semantic-search-qa (backend), Feat-0006-streamlit-ui (UI) |
| ADE, adverse drug event, drug extraction, Qwen, MLX | Feat-0001-ade-extraction-service |
| S3, SQLite, SQLAlchemy, database, registry table | Feat-0008-storage-persistence |
| Streamlit page, sidebar, login page, audit page | Feat-0006-streamlit-ui |
| audit log, DLQ viewer | Feat-0006-streamlit-ui (UI), Feat-0007-security-access-control (`audit_logger.py`), Feat-0004-pipeline-workers (`dlq.py`) |

### Per-Workflow Section-Loading Table

| Workflow | Load These Sections |
|---|---|
| Fixing a bug in one feature | that feature's Business Rules, Known Error Scenarios, Key Files |
| Adding a new role or department | Feat-0007's Access Control tables, Feat-0002's implicit schema section in `Schemas/schemas.md` |
| Changing a queue message shape | Feat-0004's Status/State Machine and Safe vs Dangerous Changes |
| Changing the DB schema | `Schemas/schemas.md` in full, plus Feat-0008's Safe vs Dangerous Changes |
| Adding a new UI page | Feat-0006's Key User Flows, UI States, and Access Control |
| Touching auth end-to-end | Feat-0007 in full, plus `.claude/rules/security.md`'s Project Auth Model |

## Dependency Graph

See [[../Architecture/Overview.md#coupling-graph-from-frontmatter-depends_onconsumed_by]] for the
full rendered graph and the highest-risk couplings. Summary of mandatory dependencies:

| Feature | Depends On | Downstream Impact If Changed |
|---|---|---|
| Feat-0001-ade-extraction-service | *(none)* | Feat-0004 loses extraction (degrades gracefully, does not fail) |
| Feat-0002-document-indexing | *(none)* | Feat-0004 can't index; Feat-0005 can't retrieve |
| Feat-0003-document-ingestion | Feat-0007, Feat-0008 | Feat-0004 has nothing to consume from `parsing_queue`; Feat-0006's upload pages break |
| Feat-0004-pipeline-workers | Feat-0001, Feat-0002, Feat-0003, Feat-0007, Feat-0008 | documents never progress past `VALIDATED` |
| Feat-0005-semantic-search-qa | Feat-0002, Feat-0007 | Feat-0006's search page has nothing to call |
| Feat-0006-streamlit-ui | Feat-0002, Feat-0003, Feat-0004, Feat-0005, Feat-0007, Feat-0008 | no consumer — this is the leaf of the graph |
| Feat-0007-security-access-control | *(none — base of the graph)* | every other feature loses auth/RBAC/masking/audit/encryption |
| Feat-0008-storage-persistence | *(none — base of the graph)* | every other feature loses S3/DB access |
