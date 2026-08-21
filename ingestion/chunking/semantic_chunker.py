"""
Split Markdown text into semantically meaningful chunks.

Strategy:
  1. Split on ## section headers → one chunk per section.
  2. If a section is still too large, split further on sentence boundaries
     with `chunk_size` token limit and `chunk_overlap` overlap.
"""
from __future__ import annotations
import re
import uuid
import logging
from dataclasses import dataclass, field
from app.config import settings

logger = logging.getLogger(__name__)


@dataclass
class Chunk:
    chunk_id: str
    doc_id: str
    text: str
    chunk_hash: str
    chunk_index: int
    section: str
    page_number: int
    parent_chunk_id: str | None = None
    metadata: dict = field(default_factory=dict)


def _split_sentences(text: str) -> list[str]:
    # Simple sentence splitter on . ! ? followed by whitespace
    return [s.strip() for s in re.split(r"(?<=[.!?])\s+", text) if s.strip()]


def _split_into_windows(sentences: list[str], size: int, overlap: int) -> list[str]:
    windows: list[str] = []
    i = 0
    while i < len(sentences):
        window_sents = sentences[i:i + size]
        windows.append(" ".join(window_sents))
        step = max(1, size - overlap)
        i += step
    return windows


def chunk_markdown(markdown_text: str, doc_id: str, page_number: int = 0) -> list[Chunk]:
    from ingestion.chunking.chunk_hasher import compute_hash

    # Split on ## headers
    sections = re.split(r"(?=^## )", markdown_text, flags=re.MULTILINE)

    chunks: list[Chunk] = []
    chunk_index = 0

    for section_text in sections:
        section_text = section_text.strip()
        if not section_text:
            continue

        # Extract section title
        header_match = re.match(r"^## (.+)$", section_text, re.MULTILINE)
        section_name = header_match.group(1).strip() if header_match else "General"

        # Remove the header line itself before chunking
        body = re.sub(r"^## .+$", "", section_text, flags=re.MULTILINE).strip()
        if not body:
            continue

        sentences = _split_sentences(body)
        # Use word count as proxy for tokens
        word_count = len(body.split())

        if word_count <= settings.chunk_size:
            # Section fits in a single chunk
            parent_id = str(uuid.uuid4())
            h = compute_hash(body)
            chunks.append(Chunk(
                chunk_id=parent_id,
                doc_id=doc_id,
                text=body,
                chunk_hash=h,
                chunk_index=chunk_index,
                section=section_name,
                page_number=page_number,
                parent_chunk_id=None,
            ))
            chunk_index += 1
        else:
            # Split into overlapping windows; first chunk is the "parent"
            windows = _split_into_windows(sentences, settings.chunk_size, settings.chunk_overlap)
            parent_id = str(uuid.uuid4())
            for i, window in enumerate(windows):
                h = compute_hash(window)
                cid = parent_id if i == 0 else str(uuid.uuid4())
                chunks.append(Chunk(
                    chunk_id=cid,
                    doc_id=doc_id,
                    text=window,
                    chunk_hash=h,
                    chunk_index=chunk_index,
                    section=section_name,
                    page_number=page_number,
                    parent_chunk_id=None if i == 0 else parent_id,
                ))
                chunk_index += 1

    logger.info("Chunked doc %s into %d chunks", doc_id, len(chunks))
    return chunks
