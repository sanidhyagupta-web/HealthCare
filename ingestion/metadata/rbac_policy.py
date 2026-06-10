"""
RBAC policy — single source of truth for department → allowed_roles mapping
and the set of roles permitted to submit documents for ingestion.

Add new roles or departments here. Never hardcode role lists anywhere else.
"""
from __future__ import annotations

_DEPARTMENT_ROLES: dict[str, list[str]] = {
    "general": ["doctor", "nurse", "admin", "researcher"],
    "cardiology": ["doctor", "nurse", "cardiologist", "researcher"],
    "billing": ["billing", "admin"],
    "radiology": ["doctor", "nurse", "radiologist", "admin"],
    "oncology": ["doctor", "nurse", "admin"],
}

# Roles allowed to submit documents via the ingest endpoints (single and bulk).
_INGEST_ALLOWED_ROLES: frozenset[str] = frozenset({"doctor", "nurse", "admin"})


def get_allowed_roles(department: str) -> list[str]:
    """Return the list of roles allowed to access chunks from *department*.

    Raises ValueError for unknown departments so mis-spelled department names
    fail loudly at ingest time rather than producing zero-access chunks.
    """
    try:
        return list(_DEPARTMENT_ROLES[department])
    except KeyError:
        raise ValueError(f"Unknown department: {department!r}. "
                         f"Valid departments: {sorted(_DEPARTMENT_ROLES)}")


def get_all_departments() -> list[str]:
    return list(_DEPARTMENT_ROLES.keys())


def get_ingest_allowed_roles() -> frozenset[str]:
    """Return the set of roles that may submit documents for ingestion."""
    return _INGEST_ALLOWED_ROLES
