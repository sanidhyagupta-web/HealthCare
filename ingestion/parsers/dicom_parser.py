"""
DICOM header parser for the Harmony ingestion pipeline.

Reads a .dcm file via pydicom (header only — pixels are never loaded),
extracts structured metadata fields, and returns a plain-text representation
that the MarkdownWorker can detect and convert to Markdown.

Return shape matches the pdf_parser contract so ParserWorker can treat
all doc types uniformly:

    {
        "text":                      str,   # key:value header dump
        "page_count":                int,   # always 1 for a single DICOM file
        "dicom_modality":            str,   # e.g. "CT", "MR", "CR"
        "dicom_study_instance_uid":  str,
        "dicom_series_instance_uid": str,
    }

Raises ValueError (→ BaseWorker DLQ path) if the bytes are not a valid DICOM file.
"""
from __future__ import annotations

import io
from typing import Any

import pydicom
from pydicom.errors import InvalidDicomError


# Ordered list of (pydicom attribute, label written to plain-text output).
# Only non-empty values are written; order determines section grouping in the
# downstream dicom_converter.
_HEADER_FIELDS: list[tuple[str, str]] = [
    ("InstitutionName",          "InstitutionName"),
    ("InstitutionAddress",       "InstitutionAddress"),
    ("Modality",                 "Modality"),
    ("StudyDate",                "StudyDate"),
    ("StudyTime",                "StudyTime"),
    ("StudyDescription",         "StudyDescription"),
    ("BodyPartExamined",         "BodyPartExamined"),
    ("AccessionNumber",          "AccessionNumber"),
    ("PatientID",                "PatientID"),
    ("PatientName",              "PatientName"),
    ("PatientBirthDate",         "PatientBirthDate"),
    ("PatientSex",               "PatientSex"),
    ("PatientAge",               "PatientAge"),
    ("ReferringPhysicianName",   "ReferringPhysicianName"),
    ("PerformingPhysicianName",  "PerformingPhysicianName"),
    ("StudyInstanceUID",         "StudyInstanceUID"),
    ("SeriesInstanceUID",        "SeriesInstanceUID"),
    ("SOPInstanceUID",           "SOPInstanceUID"),
    ("SeriesDescription",        "SeriesDescription"),
    ("SeriesNumber",             "SeriesNumber"),
    ("InstanceNumber",           "InstanceNumber"),
]


def _safe_str(value: Any) -> str:
    """Convert a pydicom value to a clean string, stripping surrounding whitespace.

    pydicom PersonName objects render as "Last^First" — left as-is so the
    PiiWorker's Presidio analyzer can detect them as PERSON entities.
    """
    if value is None:
        return ""
    return str(value).strip()


def parse_dicom(file_bytes: bytes) -> dict:
    """Extract DICOM header metadata from raw file bytes.

    Parameters
    ----------
    file_bytes:
        Raw bytes of the .dcm file (as read from S3 or from st.file_uploader).

    Returns
    -------
    dict with keys:
        text                      — plain-text key:value dump for MarkdownWorker
        page_count                — always 1
        dicom_modality            — e.g. "CT", "MR", "CR"
        dicom_study_instance_uid  — StudyInstanceUID string
        dicom_series_instance_uid — SeriesInstanceUID string

    Raises
    ------
    ValueError
        If the bytes do not represent a valid DICOM file.
    """
    try:
        ds = pydicom.dcmread(io.BytesIO(file_bytes), stop_before_pixels=True)
    except InvalidDicomError as exc:
        raise ValueError(f"Not a valid DICOM file: {exc}") from exc

    lines: list[str] = ["DICOM Study"]
    for attr, label in _HEADER_FIELDS:
        value = _safe_str(getattr(ds, attr, None))
        if value:
            lines.append(f"{label}: {value}")

    return {
        "text": "\n".join(lines),
        "page_count": 1,
        "dicom_modality":            _safe_str(getattr(ds, "Modality", "")),
        "dicom_study_instance_uid":  _safe_str(getattr(ds, "StudyInstanceUID", "")),
        "dicom_series_instance_uid": _safe_str(getattr(ds, "SeriesInstanceUID", "")),
    }
