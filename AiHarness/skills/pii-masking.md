# Skill: PII Masking

## What this covers
Two-phase PII handling: ingest-time redaction (permanent, stored) and query-time role masking (runtime, per-caller).

## Phase 1 — Ingest-time redaction (PiiWorker)

**Location:** `workers/pii_worker.py`, `ingestion/pii/pii_detector.py`, `ingestion/pii/pii_redactor.py`

**What it detects:**
- `PATIENT_NAME`, `MRN`, `DATE`, `PHONE_NUMBER`, `EMAIL_ADDRESS`, `SSN`
- Microsoft Presidio analyzer as primary; regex fallback for clinical patterns Presidio misses.

**What it does:**
1. Detect entities → get spans + types.
2. Register entity hashes to `indexing/pii_entity_index.py` — hash only, never the raw value.
3. Encrypt raw PHI values with KMS via `security/encryption.py`.
4. Replace entities in chunk text with `[ENTITY_TYPE]` placeholders.
5. Store the redacted text. The original plaintext PHI is never written to disk.

```python
# Good — correct redaction flow
from ingestion.pii.pii_detector import detect_entities
from ingestion.pii.pii_redactor import redact_text

entities = detect_entities(chunk_text)
redacted = redact_text(chunk_text, entities)
# redacted: "Patient [PATIENT_NAME] (MRN: [MRN]) admitted on [DATE]..."
```

## Phase 2 — Query-time role masking

**Location:** `ingestion/pii/role_based_masking.py`, `security/access_control.py`

Even after redaction, some roles should not see clinical content at all.

| Role | Sees clinical text | Sees metadata |
|---|---|---|
| `doctor` | Yes (redacted) | Yes |
| `nurse` | Yes (redacted) | Yes |
| `admin` | No — `[REDACTED]` | Yes |
| `billing` | Billing codes only | Yes |
| `anonymous` | No | No |

```python
# Good — apply runtime masking before returning to caller
from ingestion.pii.role_based_masking import apply_role_mask

masked_chunks = [apply_role_mask(chunk, user_role) for chunk in filtered_chunks]
```

## Entity hash index
`indexing/pii_entity_index.py` stores SHA-256 hashes of detected entities. At query time, if the query contains known entity hashes, only chunks belonging to that patient are returned (used for patient-scoped search).

## Bad examples

```python
# BAD: storing original PII alongside redacted text
chunk["raw_text"] = original_text
chunk["redacted_text"] = redacted_text  # never store raw PII in any chunk field

# BAD: skipping role masking
return filtered_chunks  # forgot apply_role_mask — admin sees full clinical text

# BAD: applying masking before RBAC filter
masked = [apply_role_mask(c, role) for c in all_chunks]
filtered = filter_results_by_role(masked, role)  # wrong order
```

## Failure modes seen
- Agent stores `raw_text` next to `redacted_text` "for debugging" — plaintext PHI persists in the store.
- Agent applies role masking before RBAC filter — RBAC then operates on `[REDACTED]` text and fails to filter correctly. Always filter first, mask second.
- Agent uses a different entity label format (`<NAME>` instead of `[PATIENT_NAME]`) — downstream citation parser breaks.

## Must NOT do
- Store raw PII values anywhere — not in chunk fields, not in logs, not in metadata.
- Apply role masking before `filter_results_by_role`.
- Invent new entity placeholder formats — always use `[ENTITY_TYPE]` (uppercase, square brackets).
- Skip PII detection because "this document is already clean" — always run Presidio.
