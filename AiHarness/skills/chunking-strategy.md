# Skill: Chunking Strategy

## What this covers
How to chunk medical documents in this repo — entity preservation, greedy packing, deduplication, and the inline handoff to PiiWorker.

## Canonical chunker
`ingestion/chunking/entity_preserving_chunker.py` — this is the **only** chunker used in the pipeline. `semantic_chunker.py` exists for reference but is not wired to any worker.

## How it works

### 1. Section split
Markdown is split on `## ` headers. Each section is chunked independently. The section name is carried into every chunk's `section` field.

### 2. Entity group detection
Lines within a section are tagged with medical entity patterns (10 types: `MEDICATION`, `DOSAGE_FREQ`, `DRUG_DOSE`, `MEAL_INSTRUCTION`, `DURATION`, `VITAL_SIGN`, `LAB_VALUE`, `ICD10`, `PATIENT_DEMOGRAPHICS`, `RX_HEADER`, `ADVISORY`). Consecutive tagged lines are merged into atomic groups that can never be split:

```
Tab. Augmentin 625mg        ← MEDICATION
1 - 0 - 1 x 5 days         ← DOSAGE_FREQ (sticky to prev)
after meals                 ← MEAL_INSTRUCTION (sticky)
```
These three lines are one group. They always land in the same chunk.

### 3. Greedy packing
Groups are greedily packed until `settings.chunk_size` (500 words) would be exceeded. A group may cause slight overflow — this is by design; groups are never split.

### 4. Short-chunk merge
Chunks under 30 words are merged forward (into the next chunk) or backward (into the last chunk) to avoid orphaned one-liners.

### 5. SHA-256 deduplication
Each chunk gets `compute_hash(text)` from `ingestion/chunking/chunk_hasher.py` (whitespace-normalized, lowercased). `ChunkingWorker` calls `register_chunk()` for each; duplicates are dropped. If *all* chunks are duplicates, document status → `DUPLICATE` and pipeline stops.

### 6. Inline handoff (no disk write)
Chunks are serialized into the queue message dict and put on `queues.pii_queue`. Plaintext PII **never touches the filesystem** between ChunkingWorker and PiiWorker.

## Chunk schema

```python
@dataclass
class Chunk:
    chunk_id: str           # UUID
    doc_id: str
    text: str               # raw (pre-redaction) text
    chunk_hash: str         # SHA-256 of normalized text
    chunk_index: int        # sequential position in doc
    section: str            # ## header text, "General" if none
    page_number: int
    parent_chunk_id: str | None   # set only for sub-chunks of a large section
    entity_types: list[str]       # detected entity type names
```

## Bad examples

```python
# BAD: using semantic_chunker instead of entity_preserving_chunker
from ingestion.chunking.semantic_chunker import chunk_markdown

# BAD: writing chunks to disk before PII redaction
with open(f"data/processed/chunks/{doc_id}.json", "w") as f:
    json.dump(chunks, f)

# BAD: fixed-size token splitting that ignores medical entities
chunks = [text[i:i+500] for i in range(0, len(text), 500)]
```

## Failure modes seen
- Agent imports `semantic_chunker` instead of `entity_preserving_chunker` — medications get split mid-block.
- Agent writes `chunks.json` to disk — plaintext PHI leaks before PII redaction.
- Agent skips `register_chunk()` — duplicates are not detected, re-ingested docs get double-indexed.

## Must NOT do
- Split a MEDICATION + DOSAGE_FREQ group across two chunks.
- Write chunks (containing plaintext PII) to any file path.
- Use a generic text splitter (LangChain `RecursiveCharacterTextSplitter`, etc.) for medical content.
- Skip dedup — always call `register_chunk()` for every chunk.
