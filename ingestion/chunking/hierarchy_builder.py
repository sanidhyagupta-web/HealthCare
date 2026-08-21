"""
Group chunks into parent-child hierarchy for improved retrieval context.
Parent = the first chunk of a section (or the section summary).
Children = subsequent sub-chunks within the same section.
"""
from __future__ import annotations
from ingestion.chunking.semantic_chunker import Chunk


def build_hierarchy(chunks: list[Chunk]) -> dict[str, list[Chunk]]:
    """
    Returns a mapping: parent_chunk_id -> [child_chunks].
    Chunks with parent_chunk_id=None are top-level parents.
    """
    hierarchy: dict[str, list[Chunk]] = {}
    for chunk in chunks:
        if chunk.parent_chunk_id:
            hierarchy.setdefault(chunk.parent_chunk_id, []).append(chunk)
    return hierarchy


def get_parent_context(chunk: Chunk, all_chunks: list[Chunk]) -> str | None:
    """Return the text of the parent chunk, if it exists."""
    if not chunk.parent_chunk_id:
        return None
    for c in all_chunks:
        if c.chunk_id == chunk.parent_chunk_id:
            return c.text
    return None
