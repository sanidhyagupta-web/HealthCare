"""
Query-time role-based masking.

Chunks are already redacted at ingest time (PiiWorker → [ENTITY_TYPE] placeholders).
This module applies a second, role-aware pass: certain roles must not see specific
placeholder tokens even in their bracketed form.

Rules
-----
- Entity type membership is determined by the ``entity_types`` field already stored
  on each chunk — never re-detected with Presidio at query time.
- Masked tokens are replaced with ``[REDACTED]`` so the chunk structure is preserved.
- Call AFTER ``filter_results_by_role``, never before.
"""
from __future__ import annotations

import re
import copy

# ---------------------------------------------------------------------------
# Per-role entity masking sets
# ---------------------------------------------------------------------------

# Entities that researchers must never see — PHI / direct identifiers.
RESEARCHER_MASKED_ENTITIES: frozenset[str] = frozenset({
    "PATIENT_NAME",
    "MRN",
    "DATE",
    "PHONE_NUMBER",
    "EMAIL_ADDRESS",
    "SSN",
    "PATIENT_DEMOGRAPHICS",
})

# admin sees no clinical content — mask everything clinical.
ADMIN_MASKED_ENTITIES: frozenset[str] = frozenset({
    "PATIENT_NAME",
    "MRN",
    "DATE",
    "PHONE_NUMBER",
    "EMAIL_ADDRESS",
    "SSN",
    "PATIENT_DEMOGRAPHICS",
    "ICD10",
    "LAB_VALUE",
    "VITAL_SIGN",
    "MEDICATION",
    "DOSAGE_FREQ",
    "DRUG_DOSE",
})

# billing sees billing codes only — mask all clinical identifiers and content.
BILLING_MASKED_ENTITIES: frozenset[str] = frozenset({
    "PATIENT_NAME",
    "MRN",
    "DATE",
    "PHONE_NUMBER",
    "EMAIL_ADDRESS",
    "SSN",
    "PATIENT_DEMOGRAPHICS",
    "LAB_VALUE",
    "VITAL_SIGN",
    "MEDICATION",
    "DOSAGE_FREQ",
    "DRUG_DOSE",
})

_ROLE_MASK_MAP: dict[str, frozenset[str]] = {
    "researcher": RESEARCHER_MASKED_ENTITIES,
    "admin": ADMIN_MASKED_ENTITIES,
    "billing": BILLING_MASKED_ENTITIES,
}

# Roles that see all redacted clinical content without further masking.
_UNMASKED_ROLES: frozenset[str] = frozenset({"doctor", "nurse", "cardiologist"})


def _mask_text(text: str, entity_types: frozenset[str]) -> str:
    """Replace ``[ENTITY_TYPE]`` tokens for the given *entity_types* with ``[REDACTED]``."""
    def _replacer(match: re.Match) -> str:
        token = match.group(1)  # e.g. "PATIENT_NAME"
        return "[REDACTED]" if token in entity_types else match.group(0)

    return re.sub(r"\[([A-Z0-9_]+)\]", _replacer, text)


def apply_role_mask(chunk: dict, role: str) -> dict:
    """Return a copy of *chunk* with entity tokens masked for *role*.

    The original chunk dict is never mutated.

    Parameters
    ----------
    chunk:
        A retrieval result dict with at least a ``text`` key and optionally
        an ``entity_types`` key listing which PII entity types appear in the text.
    role:
        The authenticated caller's role string.

    Returns
    -------
    dict
        A shallow copy of *chunk* with ``text`` rewritten and ``entity_types``
        updated to reflect remaining visible entities.
    """
    if role in _UNMASKED_ROLES:
        return chunk  # clinical staff see full redacted text — no further masking

    masked_entities = _ROLE_MASK_MAP.get(role)
    if masked_entities is None:
        # Unknown role — mask everything for safety.
        masked_entities = frozenset(
            t for t in _extract_tokens(chunk.get("text", ""))
        )

    masked = copy.copy(chunk)
    masked["text"] = _mask_text(chunk.get("text", ""), masked_entities)

    # Update entity_types to reflect what remains visible.
    original_types = set(chunk.get("entity_types") or [])
    masked["entity_types"] = sorted(original_types - masked_entities)

    return masked


def _extract_tokens(text: str) -> list[str]:
    """Return unique entity type tokens found in *text*."""
    return list({m.group(1) for m in re.finditer(r"\[([A-Z0-9_]+)\]", text)})
