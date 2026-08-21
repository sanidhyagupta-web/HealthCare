"""
DICOM header → Markdown converter for the Harmony ingestion pipeline.

Mirrors the role of prescription_converter.py: it takes the plain-text
key:value output produced by dicom_parser.parse_dicom()["text"] and
renders it as structured Markdown that the entity-preserving chunker
can split on "## " section headers.

Public API
----------
is_dicom(text: str) -> bool
    True if *text* was produced by dicom_parser (sentinel first line).

convert_dicom_to_markdown(text: str) -> str
    Parses *text*, renders structured Markdown.

Output sections
---------------
# DICOM Study Report
## Study Information      — modality, dates, description, body part, accession
## Patient Information    — patient ID/name/DOB/sex/age, referring physician
## Technical Identifiers  — UIDs (Study, Series, SOP)
"""
from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass
class _DicomData:
    institution_name: str = ""
    institution_address: str = ""
    modality: str = ""
    study_date: str = ""
    study_time: str = ""
    study_description: str = ""
    body_part: str = ""
    accession_number: str = ""
    patient_id: str = ""
    patient_name: str = ""
    patient_birth_date: str = ""
    patient_sex: str = ""
    patient_age: str = ""
    referring_physician: str = ""
    performing_physician: str = ""
    study_instance_uid: str = ""
    series_instance_uid: str = ""
    sop_instance_uid: str = ""
    series_description: str = ""
    series_number: str = ""
    instance_number: str = ""


def _field(text: str, label: str) -> str:
    """Extract the value for *label* from a "label: value" plain-text dump."""
    m = re.search(r"^" + re.escape(label) + r":\s*(.+)", text, re.MULTILINE)
    return m.group(1).strip() if m else ""


def _parse(text: str) -> _DicomData:
    d = _DicomData()
    d.institution_name     = _field(text, "InstitutionName")
    d.institution_address  = _field(text, "InstitutionAddress")
    d.modality             = _field(text, "Modality")
    d.study_date           = _field(text, "StudyDate")
    d.study_time           = _field(text, "StudyTime")
    d.study_description    = _field(text, "StudyDescription")
    d.body_part            = _field(text, "BodyPartExamined")
    d.accession_number     = _field(text, "AccessionNumber")
    d.patient_id           = _field(text, "PatientID")
    d.patient_name         = _field(text, "PatientName")
    d.patient_birth_date   = _field(text, "PatientBirthDate")
    d.patient_sex          = _field(text, "PatientSex")
    d.patient_age          = _field(text, "PatientAge")
    d.referring_physician  = _field(text, "ReferringPhysicianName")
    d.performing_physician = _field(text, "PerformingPhysicianName")
    d.study_instance_uid   = _field(text, "StudyInstanceUID")
    d.series_instance_uid  = _field(text, "SeriesInstanceUID")
    d.sop_instance_uid     = _field(text, "SOPInstanceUID")
    d.series_description   = _field(text, "SeriesDescription")
    d.series_number        = _field(text, "SeriesNumber")
    d.instance_number      = _field(text, "InstanceNumber")
    return d


def _table_rows(rows: list[tuple[str, str]]) -> list[str]:
    """Render a Markdown table from (label, value) pairs, skipping blank values."""
    lines = ["| Field | Value |", "|-------|-------|"]
    for label, val in rows:
        if val:
            lines.append(f"| {label} | {val} |")
    return lines


def _render(d: _DicomData) -> str:
    out: list[str] = ["# DICOM Study Report", ""]

    if d.institution_name:
        out.append(f"**Institution:** {d.institution_name}  ")
        if d.institution_address:
            out.append(f"**Address:** {d.institution_address}  ")
        out.append("")

    out += ["## Study Information", ""]
    out += _table_rows([
        ("Modality",            d.modality),
        ("Study Date",          d.study_date),
        ("Study Description",   d.study_description),
        ("Body Part Examined",  d.body_part),
        ("Accession Number",    d.accession_number),
        ("Series Description",  d.series_description),
        ("Series Number",       d.series_number),
        ("Instance Number",     d.instance_number),
    ])
    out.append("")

    out += ["## Patient Information", ""]
    out += _table_rows([
        ("Patient ID",            d.patient_id),
        ("Patient Name",          d.patient_name),
        ("Birth Date",            d.patient_birth_date),
        ("Sex",                   d.patient_sex),
        ("Age",                   d.patient_age),
        ("Referring Physician",   d.referring_physician),
        ("Performing Physician",  d.performing_physician),
    ])
    out.append("")

    out += ["## Technical Identifiers", ""]
    out += _table_rows([
        ("Study Instance UID",   d.study_instance_uid),
        ("Series Instance UID",  d.series_instance_uid),
        ("SOP Instance UID",     d.sop_instance_uid),
    ])
    out.append("")

    return "\n".join(out)


# ── public API ────────────────────────────────────────────────────────────────

def is_dicom(text: str) -> bool:
    """Return True if *text* was produced by dicom_parser.parse_dicom()."""
    return text.startswith("DICOM Study")


def convert_dicom_to_markdown(text: str) -> str:
    """Convert a plain-text DICOM header dump to structured Markdown."""
    return _render(_parse(text))
