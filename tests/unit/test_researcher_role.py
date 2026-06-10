"""
Tests for the researcher RBAC role and its associated PII masking rules.

Covers:
- Unit: apply_role_mask correctly removes forbidden PII tokens for researcher
- Unit: apply_role_mask preserves clinical tokens (LAB_VALUE, ICD10, etc.)
- Unit: apply_role_mask leaves doctor/nurse chunks unmodified
- Integration: filter_results_by_role allows researcher into general + cardiology
- Integration: filter_results_by_role blocks researcher from billing
- Integration: secure_results end-to-end — researcher receives masked chunks
- Integration: researcher never receives a chunk with [PATIENT_NAME] or [MRN]
"""
from __future__ import annotations

import pytest

from ingestion.pii.role_based_masking import apply_role_mask, RESEARCHER_MASKED_ENTITIES
from ingestion.metadata.rbac_policy import get_allowed_roles
from security.access_control import filter_results_by_role
from search.pipeline import secure_results


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def chunk_with_patient_name():
    return {
        "text": "Patient [PATIENT_NAME] was admitted with chest pain.",
        "entity_types": ["PATIENT_NAME"],
        "metadata": {"chunk_id": "c1", "allowed_roles": ["doctor", "nurse", "researcher"]},
    }


@pytest.fixture
def chunk_with_mrn():
    return {
        "text": "MRN: [MRN] — follow-up scheduled.",
        "entity_types": ["MRN"],
        "metadata": {"chunk_id": "c2", "allowed_roles": ["doctor", "nurse", "researcher"]},
    }


@pytest.fixture
def chunk_with_lab_value():
    return {
        "text": "HbA1c: [LAB_VALUE] — above normal range.",
        "entity_types": ["LAB_VALUE"],
        "metadata": {"chunk_id": "c3", "allowed_roles": ["doctor", "nurse", "researcher"]},
    }


@pytest.fixture
def chunk_with_mixed_entities():
    return {
        "text": (
            "Patient [PATIENT_NAME] (MRN: [MRN]) born [DATE]. "
            "Diagnosis: [ICD10]. HbA1c: [LAB_VALUE]. "
            "BP: [VITAL_SIGN]. Prescribed [MEDICATION] [DOSAGE_FREQ]."
        ),
        "entity_types": [
            "PATIENT_NAME", "MRN", "DATE",
            "ICD10", "LAB_VALUE", "VITAL_SIGN", "MEDICATION", "DOSAGE_FREQ",
        ],
        "metadata": {"chunk_id": "c4", "allowed_roles": ["doctor", "nurse", "researcher"]},
    }


@pytest.fixture
def chunk_billing_department():
    return {
        "text": "Invoice [MRN] — billed [ICD10].",
        "entity_types": ["MRN", "ICD10"],
        "metadata": {"chunk_id": "c5", "allowed_roles": ["billing", "admin"]},
    }


@pytest.fixture
def chunk_general_department():
    return {
        "text": "Routine check-up. [VITAL_SIGN] within normal range.",
        "entity_types": ["VITAL_SIGN"],
        "metadata": {"chunk_id": "c6", "allowed_roles": ["doctor", "nurse", "admin", "researcher"]},
    }


@pytest.fixture
def chunk_cardiology_department():
    return {
        "text": "Echo result: [LAB_VALUE]. Diagnosis: [ICD10].",
        "entity_types": ["LAB_VALUE", "ICD10"],
        "metadata": {"chunk_id": "c7", "allowed_roles": ["doctor", "nurse", "cardiologist", "researcher"]},
    }


# ---------------------------------------------------------------------------
# Unit: RESEARCHER_MASKED_ENTITIES definition
# ---------------------------------------------------------------------------

def test_researcher_masked_entities_contains_patient_name():
    assert "PATIENT_NAME" in RESEARCHER_MASKED_ENTITIES


def test_researcher_masked_entities_contains_mrn():
    assert "MRN" in RESEARCHER_MASKED_ENTITIES


def test_researcher_masked_entities_does_not_contain_lab_value():
    assert "LAB_VALUE" not in RESEARCHER_MASKED_ENTITIES


def test_researcher_masked_entities_does_not_contain_icd10():
    assert "ICD10" not in RESEARCHER_MASKED_ENTITIES


def test_researcher_masked_entities_does_not_contain_vital_sign():
    assert "VITAL_SIGN" not in RESEARCHER_MASKED_ENTITIES


def test_researcher_masked_entities_does_not_contain_medication():
    assert "MEDICATION" not in RESEARCHER_MASKED_ENTITIES


# ---------------------------------------------------------------------------
# Unit: apply_role_mask for researcher — forbidden tokens removed
# ---------------------------------------------------------------------------

def test_researcher_cannot_see_patient_name(chunk_with_patient_name):
    result = apply_role_mask(chunk_with_patient_name, "researcher")
    assert "[PATIENT_NAME]" not in result["text"]


def test_researcher_cannot_see_mrn(chunk_with_mrn):
    result = apply_role_mask(chunk_with_mrn, "researcher")
    assert "[MRN]" not in result["text"]


def test_researcher_patient_name_replaced_with_redacted(chunk_with_patient_name):
    result = apply_role_mask(chunk_with_patient_name, "researcher")
    assert "[REDACTED]" in result["text"]


def test_researcher_mrn_replaced_with_redacted(chunk_with_mrn):
    result = apply_role_mask(chunk_with_mrn, "researcher")
    assert "[REDACTED]" in result["text"]


def test_researcher_masked_entities_removed_from_entity_types(chunk_with_patient_name):
    result = apply_role_mask(chunk_with_patient_name, "researcher")
    assert "PATIENT_NAME" not in result.get("entity_types", [])


# ---------------------------------------------------------------------------
# Unit: apply_role_mask for researcher — visible tokens preserved
# ---------------------------------------------------------------------------

def test_researcher_can_see_lab_value(chunk_with_lab_value):
    result = apply_role_mask(chunk_with_lab_value, "researcher")
    assert "[LAB_VALUE]" in result["text"]


def test_researcher_lab_value_in_entity_types(chunk_with_lab_value):
    result = apply_role_mask(chunk_with_lab_value, "researcher")
    assert "LAB_VALUE" in result.get("entity_types", [])


def test_researcher_mixed_chunk_masks_pii_only(chunk_with_mixed_entities):
    result = apply_role_mask(chunk_with_mixed_entities, "researcher")
    assert "[PATIENT_NAME]" not in result["text"]
    assert "[MRN]" not in result["text"]
    assert "[DATE]" not in result["text"]
    assert "[ICD10]" in result["text"]
    assert "[LAB_VALUE]" in result["text"]
    assert "[VITAL_SIGN]" in result["text"]
    assert "[MEDICATION]" in result["text"]
    assert "[DOSAGE_FREQ]" in result["text"]


def test_researcher_mixed_entity_types_updated(chunk_with_mixed_entities):
    result = apply_role_mask(chunk_with_mixed_entities, "researcher")
    visible = set(result.get("entity_types", []))
    assert "PATIENT_NAME" not in visible
    assert "MRN" not in visible
    assert "DATE" not in visible
    assert "ICD10" in visible
    assert "LAB_VALUE" in visible


# ---------------------------------------------------------------------------
# Unit: apply_role_mask does not modify chunk for clinical roles
# ---------------------------------------------------------------------------

def test_doctor_sees_patient_name_unmasked(chunk_with_patient_name):
    result = apply_role_mask(chunk_with_patient_name, "doctor")
    assert result["text"] == chunk_with_patient_name["text"]


def test_nurse_sees_mrn_unmasked(chunk_with_mrn):
    result = apply_role_mask(chunk_with_mrn, "nurse")
    assert result["text"] == chunk_with_mrn["text"]


def test_apply_role_mask_does_not_mutate_original(chunk_with_patient_name):
    original_text = chunk_with_patient_name["text"]
    apply_role_mask(chunk_with_patient_name, "researcher")
    assert chunk_with_patient_name["text"] == original_text


# ---------------------------------------------------------------------------
# Unit: RBAC policy — researcher in correct departments
# ---------------------------------------------------------------------------

def test_researcher_in_general_department():
    assert "researcher" in get_allowed_roles("general")


def test_researcher_in_cardiology_department():
    assert "researcher" in get_allowed_roles("cardiology")


def test_researcher_not_in_billing_department():
    assert "researcher" not in get_allowed_roles("billing")


def test_get_allowed_roles_raises_for_unknown_department():
    with pytest.raises(ValueError, match="Unknown department"):
        get_allowed_roles("unknown_dept")


# ---------------------------------------------------------------------------
# Integration: filter_results_by_role
# ---------------------------------------------------------------------------

def test_researcher_accesses_general_chunk(chunk_general_department):
    results = filter_results_by_role([chunk_general_department], "researcher")
    assert len(results) == 1


def test_researcher_accesses_cardiology_chunk(chunk_cardiology_department):
    results = filter_results_by_role([chunk_cardiology_department], "researcher")
    assert len(results) == 1


def test_researcher_blocked_from_billing(chunk_billing_department):
    results = filter_results_by_role([chunk_billing_department], "researcher")
    assert len(results) == 0


def test_researcher_gets_general_and_cardiology_but_not_billing(
    chunk_general_department, chunk_cardiology_department, chunk_billing_department
):
    all_results = [chunk_general_department, chunk_cardiology_department, chunk_billing_department]
    results = filter_results_by_role(all_results, "researcher")
    chunk_ids = {r["metadata"]["chunk_id"] for r in results}
    assert "c6" in chunk_ids   # general
    assert "c7" in chunk_ids   # cardiology
    assert "c5" not in chunk_ids  # billing — blocked


# ---------------------------------------------------------------------------
# Integration: secure_results end-to-end (RBAC + masking)
# ---------------------------------------------------------------------------

def test_secure_results_researcher_no_patient_name_in_any_chunk(
    chunk_with_patient_name, chunk_with_lab_value
):
    """Researcher never receives a chunk containing an unmasked [PATIENT_NAME] token."""
    results = [chunk_with_patient_name, chunk_with_lab_value]
    secured = secure_results(results, "researcher")
    for chunk in secured:
        assert "[PATIENT_NAME]" not in chunk["text"], (
            f"Chunk {chunk['metadata']['chunk_id']} contains unmasked [PATIENT_NAME]"
        )


def test_secure_results_researcher_no_mrn_in_any_chunk(
    chunk_with_mrn, chunk_with_lab_value
):
    """Researcher never receives a chunk containing an unmasked [MRN] token."""
    results = [chunk_with_mrn, chunk_with_lab_value]
    secured = secure_results(results, "researcher")
    for chunk in secured:
        assert "[MRN]" not in chunk["text"], (
            f"Chunk {chunk['metadata']['chunk_id']} contains unmasked [MRN]"
        )


def test_secure_results_researcher_lab_value_preserved(chunk_with_lab_value):
    secured = secure_results([chunk_with_lab_value], "researcher")
    assert len(secured) == 1
    assert "[LAB_VALUE]" in secured[0]["text"]


def test_secure_results_researcher_blocked_from_billing(chunk_billing_department):
    secured = secure_results([chunk_billing_department], "researcher")
    assert len(secured) == 0


def test_secure_results_researcher_mixed_chunk_safe(chunk_with_mixed_entities):
    """Full pipeline: researcher gets clinical tokens but no PII."""
    secured = secure_results([chunk_with_mixed_entities], "researcher")
    assert len(secured) == 1
    text = secured[0]["text"]
    assert "[PATIENT_NAME]" not in text
    assert "[MRN]" not in text
    assert "[DATE]" not in text
    assert "[ICD10]" in text
    assert "[LAB_VALUE]" in text
    assert "[VITAL_SIGN]" in text
    assert "[MEDICATION]" in text
    assert "[DOSAGE_FREQ]" in text
