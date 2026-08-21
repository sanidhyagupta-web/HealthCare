from __future__ import annotations
from enum import Enum


class DocStatus(str, Enum):
    UPLOADED = "UPLOADED"
    VALIDATED = "VALIDATED"
    PARSING = "PARSING"
    PARSED = "PARSED"
    MARKDOWN_READY = "MARKDOWN_READY"
    CHUNKED = "CHUNKED"
    PII_PROCESSED = "PII_PROCESSED"
    EXTRACTED = "EXTRACTED"
    EMBEDDED = "EMBEDDED"
    INDEXED = "INDEXED"
    FAILED = "FAILED"
    DUPLICATE = "DUPLICATE"


VALID_TRANSITIONS: dict[DocStatus, list[DocStatus]] = {
    DocStatus.UPLOADED: [DocStatus.VALIDATED, DocStatus.FAILED],
    DocStatus.VALIDATED: [DocStatus.PARSING, DocStatus.FAILED],
    DocStatus.PARSING: [DocStatus.PARSED, DocStatus.FAILED],
    DocStatus.PARSED: [DocStatus.MARKDOWN_READY, DocStatus.FAILED],
    DocStatus.MARKDOWN_READY: [DocStatus.CHUNKED, DocStatus.FAILED],
    DocStatus.CHUNKED: [DocStatus.PII_PROCESSED, DocStatus.DUPLICATE, DocStatus.FAILED],
    DocStatus.PII_PROCESSED: [DocStatus.EXTRACTED, DocStatus.FAILED],
    DocStatus.EXTRACTED: [DocStatus.EMBEDDED, DocStatus.FAILED],
    DocStatus.EMBEDDED: [DocStatus.INDEXED, DocStatus.FAILED],
    DocStatus.INDEXED: [],
    DocStatus.FAILED: [DocStatus.PARSING],  # allow retry from FAILED
    DocStatus.DUPLICATE: [],
}


def can_transition(current: DocStatus, target: DocStatus) -> bool:
    return target in VALID_TRANSITIONS.get(current, [])
