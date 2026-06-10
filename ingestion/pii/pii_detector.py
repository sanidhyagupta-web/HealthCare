"""
PII detection using Microsoft Presidio with regex fallback.

Detects: PATIENT_NAME, MRN, DATE, PHONE_NUMBER, EMAIL_ADDRESS, SSN.
"""
from __future__ import annotations
import re
import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)

_presidio_available: bool | None = None  # None = unchecked

# Whole-match patterns — the entire match is the PII span
_PATTERNS: dict[str, re.Pattern] = {
    "PHONE_NUMBER": re.compile(
        r"(?:\+?1[\s.\-]?)?\(?\d{3}\)?[\s.\-]?\d{3}[\s.\-]?\d{4}"
    ),
    "EMAIL_ADDRESS": re.compile(
        r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}"
    ),
    "DATE": re.compile(
        r"\d{1,2}[/\-]\d{1,2}[/\-]\d{2,4}"
    ),
    "SSN": re.compile(
        r"\d{3}\-\d{2}\-\d{4}"
    ),
}

# Group-based patterns — group(1) is the PII span, allowing a non-PII label prefix
_GROUP_PATTERNS: dict[str, re.Pattern] = {
    "PATIENT_NAME": re.compile(
        r"(?:Patient\s+Name|Name)\s*:\s*([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)"
    ),
    "MRN": re.compile(
        r"MRN\s*:\s*([A-Z0-9]{4,12})"
    ),
}

# Clinical expressions that Presidio mis-tags — never treat these as PII.
# ICD-10 codes (e.g. R52, M79.3) are diagnosis codes, not locations.
# Dosage frequencies (e.g. "every 6 hours", "twice daily") are clinical
# instructions, not dates/times.
_ICD10_RE = re.compile(r"\b[A-Z]\d{2}(?:\.\d{1,4})?\b")
_DOSAGE_FREQ_RE = re.compile(
    r"\b(?:every\s+\d+\s+(?:hours?|days?|weeks?|months?)"
    r"|once\s+daily|twice\s+daily|three\s+times\s+daily"
    r"|\d+\s+times?\s+(?:a\s+)?daily"
    r"|(?:once|twice|thrice)\s+(?:a\s+)?(?:day|week|month))\b",
    re.IGNORECASE,
)


def _is_false_positive(
    entity: "PiiEntity",
    text: str,
    person_spans: list[tuple[int, int]] | None = None,
    known_first_names: set[str] | None = None,
) -> bool:
    """Return True if the entity is a known clinical false positive."""
    span = text[entity.start:entity.end].strip()

    # ICD-10 codes (e.g. R52, M79.3) — Presidio may tag as LOCATION, US_DRIVER_LICENSE, etc.
    if _ICD10_RE.fullmatch(span):
        return True

    # Dosage frequency expressions mis-tagged as dates
    if entity.entity_type in ("DATE_TIME", "DATE"):
        if _DOSAGE_FREQ_RE.search(span):
            return True

    if entity.entity_type == "LOCATION":
        # LOCATION span that is fully contained within a detected PERSON span
        if person_spans:
            for ps, pe in person_spans:
                if ps <= entity.start and entity.end <= pe:
                    return True
        # Single-word LOCATION whose text is a known first name from this document
        # e.g. "Charlotte" in "Hello Charlotte," when "Charlotte Brown" is the patient
        if known_first_names and span.lower() in known_first_names:
            return True

    return False


@dataclass
class PiiEntity:
    entity_type: str
    start: int
    end: int
    text: str
    score: float


def detect_pii(text: str) -> list[PiiEntity]:
    global _presidio_available
    entities: list[PiiEntity] = []

    if _presidio_available is None:
        try:
            from presidio_analyzer import AnalyzerEngine  # noqa: F401
            _presidio_available = True
        except ImportError:
            _presidio_available = False
            logger.warning("presidio_analyzer not installed; using regex fallback")

    if _presidio_available:
        try:
            from presidio_analyzer import AnalyzerEngine
            analyzer = AnalyzerEngine()
            results = analyzer.analyze(text=text, language="en")
            for r in results:
                entities.append(PiiEntity(
                    entity_type=r.entity_type,
                    start=r.start,
                    end=r.end,
                    text=text[r.start:r.end],
                    score=r.score,
                ))
            logger.debug("Presidio detected %d PII entities", len(entities))
        except Exception as exc:
            logger.error("Presidio error: %s; falling back to regex", exc)
            _presidio_available = False

    # Always run medical-specific regex patterns (Presidio doesn't cover MRN,
    # patient name labels, or domain-specific date formats)
    if not _presidio_available:
        for entity_type, pattern in _PATTERNS.items():
            for match in pattern.finditer(text):
                entities.append(PiiEntity(
                    entity_type=entity_type,
                    start=match.start(),
                    end=match.end(),
                    text=match.group(),
                    score=0.85,
                ))

    for entity_type, pattern in _GROUP_PATTERNS.items():
        for match in pattern.finditer(text):
            entities.append(PiiEntity(
                entity_type=entity_type,
                start=match.start(1),
                end=match.end(1),
                text=match.group(1),
                score=0.85,
            ))

    # Build person spans + first-name set — used to suppress first-name-as-city false positives.
    # e.g. "Charlotte Brown" detected as PERSON → "charlotte" added to known_first_names,
    # so "Charlotte" tagged as LOCATION elsewhere in the same document is dropped.
    person_spans = [(e.start, e.end) for e in entities if e.entity_type in ("PERSON", "PATIENT_NAME")]
    known_first_names: set[str] = set()
    for e in entities:
        if e.entity_type in ("PERSON", "PATIENT_NAME"):
            tokens = e.text.strip().split()
            if len(tokens) >= 2:
                known_first_names.add(tokens[0].lower())

    # Drop known clinical false positives before dedup
    entities = [e for e in entities if not _is_false_positive(e, text, person_spans, known_first_names)]

    # Deduplicate: remove overlapping spans (keep highest score) and exact
    # value duplicates at different offsets for DATE_TIME (same date repeated
    # in a document is not additional PII — one redaction is sufficient context).
    entities.sort(key=lambda e: (e.start, -e.score))
    deduped: list[PiiEntity] = []
    last_end = -1
    seen_values: set[tuple[str, str]] = set()
    for e in entities:
        key = (e.entity_type, e.text.strip().lower())
        if e.start >= last_end and key not in seen_values:
            deduped.append(e)
            last_end = e.end
            seen_values.add(key)

    return deduped
