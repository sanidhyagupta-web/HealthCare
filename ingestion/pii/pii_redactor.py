"""Replace detected PII spans with type-labelled placeholders."""
from __future__ import annotations
import logging
from ingestion.pii.pii_detector import PiiEntity

logger = logging.getLogger(__name__)

_LABEL_MAP = {
    "PERSON": "[PATIENT_NAME]",
    "PATIENT_NAME": "[PATIENT_NAME]",
    "MEDICAL_RECORD": "[MRN]",
    "MRN": "[MRN]",
    "DATE_TIME": "[DATE]",
    "DATE": "[DATE]",
    "PHONE_NUMBER": "[PHONE]",
    "LOCATION": "[LOCATION]",
    "EMAIL_ADDRESS": "[EMAIL]",
    "SSN": "[SSN]",
    "US_SSN": "[SSN]",
    "URL": "[URL]",
}


def redact_text(text: str, entities: list[PiiEntity]) -> str:
    if not entities:
        return text

    # Sort by start offset descending so replacements don't shift later indices
    sorted_entities = sorted(entities, key=lambda e: e.start, reverse=True)
    result = list(text)

    for entity in sorted_entities:
        label = _LABEL_MAP.get(entity.entity_type, f"[{entity.entity_type}]")
        result[entity.start:entity.end] = list(label)

    redacted = "".join(result)
    logger.debug("Redacted %d PII entities", len(entities))
    return redacted
