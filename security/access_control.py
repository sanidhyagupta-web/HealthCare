"""
Query-time RBAC filter.

Filters retrieval results to those the caller is allowed to see, based on
the ``allowed_roles`` list written into each chunk's metadata at ingest time
by the PiiWorker (via ``ingestion/metadata/rbac_policy.py``).

Call order (non-negotiable, per skills/access-control.md):
    filter_results_by_role  →  apply_role_mask  →  generate_answer
"""
from __future__ import annotations


def filter_results_by_role(results: list[dict], user_role: str) -> list[dict]:
    """Return only chunks the *user_role* is allowed to access.

    ``admin`` has universal read access to metadata but role masking still
    applies downstream — this function does NOT skip masking for admin.

    Parameters
    ----------
    results:
        List of retrieval result dicts, each with a ``metadata`` key that
        contains an ``allowed_roles`` list.
    user_role:
        The authenticated caller's role string.

    Returns
    -------
    list[dict]
        Filtered list — empty if the caller has no matching chunks.
    """
    return [
        r for r in results
        if user_role in r["metadata"].get("allowed_roles", [])
        or user_role == "admin"
    ]
