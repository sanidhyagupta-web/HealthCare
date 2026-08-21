"""
Search pipeline — post-retrieval security layer.

Enforces the mandatory call order defined in skills/access-control.md:

    reranked_results
      → filter_results_by_role   (RBAC — drops forbidden chunks entirely)
      → apply_role_mask           (PII masking — redacts forbidden tokens)
      → caller receives chunks

This module contains NO retrieval logic. It is called after the vector + BM25
retrieval and reranking stages have produced their candidate list.
"""
from __future__ import annotations

from security.access_control import filter_results_by_role
from ingestion.pii.role_based_masking import apply_role_mask


def secure_results(results: list[dict], user_role: str) -> list[dict]:
    """Apply RBAC filter then role masking to *results* for *user_role*.

    Parameters
    ----------
    results:
        Reranked retrieval results. Each item must have:
        - ``metadata`` dict with ``allowed_roles: list[str]``
        - ``text`` string (already ingest-time redacted)
        - ``entity_types`` list (optional — populated at ingest time)
    user_role:
        Authenticated caller role. Must be a string from the RBAC policy.

    Returns
    -------
    list[dict]
        RBAC-filtered and role-masked chunks safe to pass to the LLM and
        return to the caller.
    """
    allowed = filter_results_by_role(results, user_role)
    return [apply_role_mask(chunk, user_role) for chunk in allowed]
