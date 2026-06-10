"""Shared schema / field definitions for both Chroma and BM25 indexes."""
from __future__ import annotations
REQUIRED_METADATA_FIELDS = [
    "patient_id",
    "doc_id",
    "chunk_id",
    "source_file",
    "source_page",
    "source_section",
    "chunk_index",
    "department",
    "allowed_roles",
]


def validate_metadata(meta: dict) -> list[str]:
    """Returns list of missing fields."""
    return [f for f in REQUIRED_METADATA_FIELDS if f not in meta]
