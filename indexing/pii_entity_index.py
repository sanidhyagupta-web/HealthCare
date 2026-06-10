"""
PII Entity Hash Index.

Maps SHA256(entity_type:entity_value) → [chunk_ids].

Key design decision for PATIENT_NAME / PERSON entities:
  A patient name appears only in the demographics/header chunk, but a query
  like "What medications is Audrey Collins taking?" should search ALL chunks
  of that patient's document — not just the header chunk.

  Solution: a parallel doc-level index maps doc_id → [all chunk_ids].
  When a PERSON/PATIENT_NAME entity matches, we expand the hit set to every
  chunk in the same document.

  All other entity types (MRN, DATE, PHONE, etc.) return only the specific
  chunk(s) where they physically appear.

The index stores only hashes — no plaintext PII is persisted here.
"""
from __future__ import annotations
import hashlib
import json
import logging
import threading
from app.config import settings

logger = logging.getLogger(__name__)

_INDEX_FILE     = settings.data_dir / "pii_entity_index.json"
_DOC_INDEX_FILE = settings.data_dir / "pii_doc_index.json"

_index: dict[str, list[str]] = {}        # sha256_hash  → [chunk_id, ...]
_doc_chunks: dict[str, list[str]] = {}   # doc_id       → [chunk_id, ...]
_chunk_doc: dict[str, str] = {}          # chunk_id     → doc_id
_lock = threading.Lock()

# Entity types whose hash match should expand to the whole document
_PATIENT_ENTITY_TYPES = {"PERSON", "PATIENT_NAME"}


def _entity_hash(entity_type: str, entity_text: str) -> str:
    key = f"{entity_type.lower()}:{entity_text.lower().strip()}"
    return hashlib.sha256(key.encode()).hexdigest()


def _save() -> None:
    _INDEX_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(_INDEX_FILE, "w") as f:
        json.dump(_index, f)
    with open(_DOC_INDEX_FILE, "w") as f:
        json.dump({"doc_chunks": _doc_chunks, "chunk_doc": _chunk_doc}, f)


def _load() -> None:
    global _index, _doc_chunks, _chunk_doc
    if _INDEX_FILE.exists():
        with open(_INDEX_FILE) as f:
            _index = json.load(f)
    if _DOC_INDEX_FILE.exists():
        with open(_DOC_INDEX_FILE) as f:
            data = json.load(f)
            _doc_chunks = data.get("doc_chunks", {})
            _chunk_doc  = data.get("chunk_doc", {})
    if _index:
        logger.info(
            "Loaded PII entity index: %d hashes, %d docs",
            len(_index), len(_doc_chunks),
        )


def register_entities(chunk_id: str, doc_id: str, entities: list) -> None:
    """
    Register PII entity hashes for a chunk.
    Called during ingestion with raw PiiEntity objects BEFORE encryption.

    Args:
        chunk_id: the chunk being processed
        doc_id:   the document this chunk belongs to
        entities: list of PiiEntity (entity_type, text, ...)
    """
    with _lock:
        # Maintain doc ↔ chunk mappings
        _chunk_doc[chunk_id] = doc_id
        doc_list = _doc_chunks.setdefault(doc_id, [])
        if chunk_id not in doc_list:
            doc_list.append(chunk_id)

        changed = False
        for e in entities:
            h = _entity_hash(e.entity_type, e.text)
            entry = _index.setdefault(h, [])
            if chunk_id not in entry:
                entry.append(chunk_id)
                changed = True

        if changed:
            _save()


def get_chunk_ids_for_entities(entities: list) -> set[str]:
    """
    Given PiiEntity objects detected from a user query, return the filtered
    set of chunk_ids to search over (Top-D selection).

    PERSON / PATIENT_NAME hits → expand to all chunks of the matched document(s).
    All other entity types    → return only the specific matching chunk(s).
    """
    if not _index:
        _load()

    matched: set[str] = set()
    for e in entities:
        h = _entity_hash(e.entity_type, e.text)
        hits = _index.get(h, [])
        if not hits:
            continue

        if e.entity_type.upper() in _PATIENT_ENTITY_TYPES:
            # Expand: collect every chunk from the same document(s)
            for chunk_id in hits:
                doc_id = _chunk_doc.get(chunk_id)
                if doc_id:
                    matched.update(_doc_chunks.get(doc_id, []))
                else:
                    matched.add(chunk_id)
        else:
            matched.update(hits)

    return matched


_load()
