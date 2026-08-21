"""
Unit tests for the DICOM ingestion components.

All tests use pydicom's bundled CT_small.dcm test file — no synthetic
patient data is created inline (per the non-negotiables in Agents.md).
"""
from __future__ import annotations

import pytest
from pathlib import Path
from pydicom.data import get_testdata_file

from ingestion.parsers.dicom_parser import parse_dicom
from ingestion.parsers.doc_type_detector import detect_doc_type
from ingestion.markdown.dicom_converter import is_dicom, convert_dicom_to_markdown


# ── fixture ───────────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def ct_bytes() -> bytes:
    return Path(get_testdata_file("CT_small.dcm")).read_bytes()


@pytest.fixture(scope="module")
def ct_result(ct_bytes) -> dict:
    return parse_dicom(ct_bytes)


# ── parse_dicom: return shape ──────────────────────────────────────────────────

def test_returns_required_keys(ct_result):
    assert "text" in ct_result
    assert "page_count" in ct_result
    assert "dicom_modality" in ct_result
    assert "dicom_study_instance_uid" in ct_result
    assert "dicom_series_instance_uid" in ct_result


def test_page_count_is_one(ct_result):
    assert ct_result["page_count"] == 1


# ── parse_dicom: field extraction ─────────────────────────────────────────────

def test_extracts_modality(ct_result):
    assert ct_result["dicom_modality"] == "CT"


def test_modality_appears_in_text(ct_result):
    assert "Modality: CT" in ct_result["text"]


def test_institution_name_in_text(ct_result):
    # CT_small.dcm has InstitutionName = "JFK IMAGING CENTER"
    assert "JFK IMAGING CENTER" in ct_result["text"]


def test_study_instance_uid_non_empty(ct_result):
    assert ct_result["dicom_study_instance_uid"] != ""


def test_series_instance_uid_non_empty(ct_result):
    assert ct_result["dicom_series_instance_uid"] != ""


def test_uids_appear_in_text(ct_result):
    assert ct_result["dicom_study_instance_uid"] in ct_result["text"]
    assert ct_result["dicom_series_instance_uid"] in ct_result["text"]


def test_text_sentinel_line(ct_result):
    assert ct_result["text"].splitlines()[0] == "DICOM Study"


# ── parse_dicom: error handling ────────────────────────────────────────────────

def test_raises_on_invalid_bytes():
    with pytest.raises(ValueError, match="Not a valid DICOM file"):
        parse_dicom(b"this is not a dicom file at all")


def test_raises_on_empty_bytes():
    with pytest.raises(ValueError, match="Not a valid DICOM file"):
        parse_dicom(b"")


# ── is_dicom ──────────────────────────────────────────────────────────────────

def test_is_dicom_true_for_parser_output(ct_result):
    assert is_dicom(ct_result["text"]) is True


def test_is_dicom_false_for_prescription():
    rx_text = "Prescription (Rx)\nHospital: Mercy General"
    assert is_dicom(rx_text) is False


def test_is_dicom_false_for_plain_text():
    assert is_dicom("Patient: John Doe\nDiagnosis: Hypertension") is False


# ── convert_dicom_to_markdown ──────────────────────────────────────────────────

def test_markdown_has_top_level_header(ct_result):
    md = convert_dicom_to_markdown(ct_result["text"])
    assert "# DICOM Study Report" in md


def test_markdown_has_study_section(ct_result):
    md = convert_dicom_to_markdown(ct_result["text"])
    assert "## Study Information" in md


def test_markdown_has_patient_section(ct_result):
    md = convert_dicom_to_markdown(ct_result["text"])
    assert "## Patient Information" in md


def test_markdown_has_uid_section(ct_result):
    md = convert_dicom_to_markdown(ct_result["text"])
    assert "## Technical Identifiers" in md


def test_markdown_contains_modality(ct_result):
    md = convert_dicom_to_markdown(ct_result["text"])
    assert "CT" in md


def test_markdown_contains_study_uid(ct_result):
    md = convert_dicom_to_markdown(ct_result["text"])
    assert ct_result["dicom_study_instance_uid"] in md


def test_markdown_contains_institution(ct_result):
    md = convert_dicom_to_markdown(ct_result["text"])
    assert "JFK IMAGING CENTER" in md


def test_markdown_table_format(ct_result):
    md = convert_dicom_to_markdown(ct_result["text"])
    assert "| Field | Value |" in md
    assert "|-------|-------|" in md


# ── doc_type_detector ─────────────────────────────────────────────────────────

def test_detects_dcm_extension():
    assert detect_doc_type("scan.dcm") == "dicom"


def test_detects_dcm_case_insensitive():
    assert detect_doc_type("scan.DCM") == "dicom"


def test_detects_pdf():
    assert detect_doc_type("report.pdf") == "pdf_typed"


def test_detects_txt():
    assert detect_doc_type("notes.txt") == "text"


def test_detects_text_extension():
    assert detect_doc_type("notes.text") == "text"


def test_raises_on_unsupported_extension():
    with pytest.raises(ValueError, match="Unsupported file extension"):
        detect_doc_type("image.png")


def test_dcm_magic_bytes_valid(ct_bytes):
    # A real DICOM file should pass magic byte validation
    result = detect_doc_type("scan.dcm", file_bytes=ct_bytes)
    assert result == "dicom"


def test_dcm_magic_bytes_invalid():
    # File named .dcm but with wrong magic bytes should raise
    fake_bytes = b"\x00" * 128 + b"XXXX" + b"\x00" * 100
    with pytest.raises(ValueError, match="DICOM preamble magic bytes"):
        detect_doc_type("fake.dcm", file_bytes=fake_bytes)


def test_dcm_no_magic_bytes_skips_validation():
    # When file_bytes not provided, magic check is skipped
    result = detect_doc_type("scan.dcm", file_bytes=None)
    assert result == "dicom"


# ── PII field presence (flows to PiiWorker) ────────────────────────────────────

def test_patient_id_in_text(ct_result):
    # PatientID must appear in text so PiiWorker can detect and redact it
    assert "PatientID:" in ct_result["text"]


def test_patient_name_in_text(ct_result):
    # PatientName must appear so Presidio can detect it as PERSON
    assert "PatientName:" in ct_result["text"]
