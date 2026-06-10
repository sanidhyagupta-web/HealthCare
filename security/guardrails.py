"""
Input and output guardrails for HIPAA-compliant query processing.

Input:  blocks prompt injection, system-prompt extraction, jailbreak attempts.
Output: masks any residual PII in LLM responses before they reach the user.
"""
from __future__ import annotations
import re
import logging

logger = logging.getLogger(__name__)

_INJECTION_PATTERNS = [
    r"ignore\s+(previous|prior|all|above)\s+instructions",
    r"reveal\s+(your\s+)?(system\s+prompt|api\s+key|instructions|prompt)",
    r"what\s+(is|are)\s+(your\s+)?(system\s+prompt|instructions|api\s+key)",
    r"forget\s+(everything|all|previous)",
    r"you\s+are\s+now\s+(a|an)",
    r"pretend\s+(you\s+are|to\s+be)",
    r"act\s+as\s+(if\s+you\s+are|a|an)",
    r"jailbreak",
    r"DAN\s+mode",
    r"bypass\s+(safety|guardrail|filter|restriction)",
    r"print\s+(your\s+)?(system\s+prompt|api\s+key|instructions)",
    r"show\s+(me\s+)?(your\s+)?(system\s+prompt|api\s+key)",
    r"repeat\s+the\s+(words|text|prompt)\s+above",
    r"output\s+(your\s+)?(initialization|system|prompt)",
    r"disregard\s+(all|previous|prior)\s+(rules|instructions|constraints)",
]

_COMPILED = [re.compile(p, re.IGNORECASE) for p in _INJECTION_PATTERNS]


def check_input(query: str) -> tuple[bool, str]:
    """
    Returns (is_safe, reason).
    is_safe=False → query should be blocked.
    """
    for pattern in _COMPILED:
        if pattern.search(query):
            logger.warning("Input guardrail blocked query pattern: %r", query[:120])
            return False, "Your query contains disallowed content and cannot be processed."
    return True, ""


def sanitise_output(text: str) -> str:
    """
    Final HIPAA compliance pass on LLM output.
    Detects and masks any PII that slipped through into the generated answer.
    """
    from ingestion.pii.pii_detector import detect_pii
    from ingestion.pii.pii_redactor import redact_text

    entities = detect_pii(text)
    if entities:
        logger.info(
            "Output guardrail masked %d PII entity/entities in LLM response", len(entities)
        )
        return redact_text(text, entities)
    return text
