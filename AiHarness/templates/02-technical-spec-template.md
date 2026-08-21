# Technical Spec — [Feature Name]

> Copy to `features/active/<feature-name>/02-technical-spec.md`.
> Fill after 01-product-spec.md is approved.

## Architecture Decision
_Where does this feature live in the pipeline? Check one:_
- [ ] Ingestion (new worker stage or parser type)
- [ ] Chunking / embedding (changes to indexing)
- [ ] Search / retrieval (changes to query path)
- [ ] Security / RBAC (new role, masking rule, or permission)
- [ ] LLM response (new prompt, output format, or validation)
- [ ] UI (Streamlit page)
- [ ] Evaluation / observability

## Components Touched

| File / Module | Change type | Notes |
|---|---|---|
| `workers/` | New worker / extend existing | |
| `ingestion/` | New parser / chunker variant | |
| `indexing/` | New store or retrieval path | |
| `security/` | RBAC or audit change | |
| `db/models.py` | New table / column | |
| `app/config.py` | New settings key | |

## Data Model Changes
_New tables, new columns, or schema changes. If none, say "None"._

```sql
-- Example
ALTER TABLE document_registry ADD COLUMN dicom_series_id TEXT;
```

## API / Interface Surface
_New queue message schema, new function signatures, new Streamlit widget._

```python
# New queue message shape (if applicable)
{
    "doc_id": str,
    "new_field": str,
    # ...
}
```

## Skills Required
_List every skill file from `skills/` that applies to this feature._

- `skills/document-ingestion.md`
- `skills/chunking-strategy.md`
- _(add more as needed)_

## Non-Negotiables Checklist
- [ ] PII redacted before any disk write of chunk content
- [ ] `allowed_roles` present in all Chroma metadata
- [ ] Audit log event emitted for every new ingestion or search event
- [ ] `update_status()` called at each stage transition
- [ ] No hardcoded credentials or patient IDs
- [ ] BaseWorker retry pattern used for any new worker

## Risks & Unknowns

| Risk | Likelihood | Mitigation |
|---|---|---|
| | | |
