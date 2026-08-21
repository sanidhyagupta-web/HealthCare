"""
Prescription-aware markdown converter for healthcare Rx PDFs.

Two layout variants are handled:
  Layout A (Mercy General, St. Mary's, Johns Hopkins):
    Patient fields are on separate label/value lines (Name:\nSamuel King).
    Medications are in a table: each row is three consecutive lines
    (med name, dosage, frequency).

  Layout B (Cedar-Sinai, Mayo Clinic):
    Patient fields are inline (Patient: Aria Johnson).
    Medications are numbered narrative items that may span multiple lines.
"""
from __future__ import annotations
import re
from dataclasses import dataclass, field


@dataclass
class _Med:
    name: str
    dosage: str = ""
    frequency: str = ""
    full_text: str = ""  # used for Layout B narrative items


@dataclass
class _RxData:
    hospital: str = ""
    address: str = ""
    patient_name: str = ""
    patient_age: str = ""
    date: str = ""
    mrn: str = ""
    diagnosis: str = ""
    medications: list[_Med] = field(default_factory=list)
    medication_notes: str = ""
    patient_instructions: str = ""
    physician: str = ""
    physician_date: str = ""


# ── helpers ──────────────────────────────────────────────────────────────────

def _strip_page_artifacts(text: str, hospital: str, address: str) -> str:
    """Remove page-number footers and repeated per-page hospital headers."""
    text = re.sub(r"\nPage \d+\n?", "\n", text)
    if hospital and address:
        repeated = re.escape(hospital) + r"\n" + re.escape(address) + r"\n"
        parts = re.split(repeated, text, maxsplit=0, flags=re.MULTILINE)
        if len(parts) > 1:
            # Keep the first occurrence's header block; drop the rest
            text = parts[0] + hospital + "\n" + address + "\n" + "\n".join(parts[1:])
    # Collapse multiple blank lines left by page-break joins
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text


def _val_after(text: str, label: str) -> str:
    """Return the value on the line immediately following 'label:' (Layout A)."""
    m = re.search(re.escape(label) + r":\n(.+)", text)
    return m.group(1).strip() if m else ""


def _inline_val(text: str, label: str) -> str:
    """Return the value on the same line as 'label:' (Layout B)."""
    m = re.search(re.escape(label) + r":\s*(.+)", text)
    return m.group(1).strip() if m else ""


# ── layout A ─────────────────────────────────────────────────────────────────

def _parse_layout_a(text: str) -> _RxData:
    data = _RxData()
    lines = [l for l in text.splitlines() if l.strip()]

    data.hospital = lines[0] if lines else ""
    data.address = lines[1] if len(lines) > 1 else ""

    data.patient_name = _val_after(text, "Name")
    data.patient_age  = _val_after(text, "Age")
    data.date         = _val_after(text, "Date")
    data.mrn          = _val_after(text, "MRN")

    # Diagnosis may appear as "Diagnosis:\n<value>" or "Diagnosis: <value>"
    diag_m = re.search(r"Diagnosis:\n?(.+)", text)
    if diag_m:
        data.diagnosis = diag_m.group(1).strip()

    # Medication table: after "Prescribed Medications:\n[header row]\n"
    # Each row is three consecutive lines: name, dosage, frequency.
    # Rows may be numbered ("1. Gabapentin") or unnumbered ("Naproxen").
    med_start = re.search(r"Prescribed Medications:\n", text)
    med_end   = re.search(r"\nPatient Instructions:", text)
    if med_start and med_end:
        med_block = text[med_start.end():med_end.start()]
        # Drop the column-header row
        med_block = re.sub(r"^Medication\nDosage\nFrequency\n", "", med_block)
        parts = [p.strip() for p in med_block.splitlines() if p.strip()]
        numbered = any(re.match(r"\d+\.", p) for p in parts)
        i = 0
        while i + 2 < len(parts):
            if numbered and not re.match(r"\d+\.", parts[i]):
                i += 1
                continue
            name   = re.sub(r"^\d+\.\s*", "", parts[i])
            dosage = parts[i + 1]
            freq   = parts[i + 2]
            # Safety: skip if dosage/freq look like another item header
            if re.match(r"\d+\.", dosage) or re.match(r"\d+\.", freq):
                i += 1
                continue
            data.medications.append(_Med(name=name, dosage=dosage, frequency=freq))
            i += 3

    instr_m = re.search(r"Patient Instructions:\n(.*?)(?=Prescribing Physician:|$)", text, re.DOTALL)
    if instr_m:
        data.patient_instructions = instr_m.group(1).strip()

    phys_m = re.search(r"Prescribing Physician:\s*(.+)", text)
    if phys_m:
        data.physician = phys_m.group(1).strip()

    dates = re.findall(r"\bDate:\s*(\d{4}-\d{2}-\d{2})", text)
    data.physician_date = dates[-1] if dates else ""

    return data


# ── layout B ─────────────────────────────────────────────────────────────────

def _parse_layout_b(text: str) -> _RxData:
    data = _RxData()
    lines = [l for l in text.splitlines() if l.strip()]

    data.hospital = lines[0] if lines else ""
    data.address = lines[1] if len(lines) > 1 else ""

    data.patient_name = _inline_val(text, "Patient")
    data.patient_age  = _inline_val(text, "Age")
    data.date         = _inline_val(text, "Date")
    data.mrn          = _inline_val(text, "MRN")
    data.diagnosis    = _inline_val(text, "Diagnosis")

    # Medication block between "Medication and Instructions:" and "Patient Instructions:"
    med_start = re.search(r"Medication and Instructions:\n", text)
    med_end   = re.search(r"\nPatient Instructions:", text)
    if med_start and med_end:
        med_block = text[med_start.end():med_end.start()].strip()

        # Strip repeated patient-header lines that some layouts embed here
        med_block = re.sub(r"Patient:\s*.+\n", "", med_block)
        med_block = re.sub(r"Age:\s*.+\n", "", med_block)
        med_block = re.sub(r"Diagnosis:\s*.+\n", "", med_block)
        med_block = re.sub(r"Prescription:\n", "", med_block)

        # Skip intro line like "Prescription for <Patient>, <age> years old, <diagnosis>:"
        med_block = re.sub(r"^Prescription for .+:\n", "", med_block)

        # Capture trailing notes ("Please follow up…" / "Note: …")
        notes_m = re.search(r"\n((?:Please|Note):.+)$", med_block, re.DOTALL)
        if notes_m:
            data.medication_notes = " ".join(notes_m.group(1).split())
            med_block = med_block[:notes_m.start()]

        if re.search(r"Medication \d+", med_block):
            # Labeled sub-item format: "Medication N:\n- Name: ...\n- Dosage: ...\n- Frequency: ..."
            # Split on "Medication N[optional suffix]:" whether it appears at the start or after \n
            blocks = re.split(r"(?:^|\n)Medication \d+[^:]*:", med_block)
            for block in blocks[1:]:
                # Join continuation lines (no leading "-") onto the preceding sub-item
                sub_items: list[str] = []
                for raw in block.strip().splitlines():
                    stripped = raw.strip()
                    if not stripped:
                        continue
                    if stripped.startswith("-"):
                        sub_items.append(re.sub(r"^-\s*", "", stripped))
                    elif sub_items:
                        sub_items[-1] += " " + stripped
                name = dosage = freq = ""
                for item in sub_items:
                    lc = item.lower()
                    if lc.startswith("dosage:"):
                        dosage = re.sub(r"(?i)dosage:\s*", "", item).strip()
                    elif lc.startswith("frequency:"):
                        freq = re.sub(r"(?i)frequency:\s*", "", item).strip()
                    elif not name:
                        # Strip leading type label ("Inhaler:", "Controller Medication:", etc.)
                        name = re.sub(r"^[A-Za-z ]+:\s*", "", item).strip()
                data.medications.append(_Med(name=name, dosage=dosage, frequency=freq))
        else:
            # Standard numbered narrative items: "1. Medication text spanning one or more lines"
            raw_items = re.split(r"\n(?=\d+\.)", med_block.strip())
            for item in raw_items:
                item = item.strip()
                if not item or not re.match(r"\d+\.", item):
                    continue
                item_text = " ".join(re.sub(r"^\d+\.\s*", "", item).split("\n"))
                item_text = " ".join(item_text.split())
                data.medications.append(_Med(name="", full_text=item_text))

    instr_m = re.search(r"Patient Instructions:\n(.*?)(?=Prescribing Physician:|$)", text, re.DOTALL)
    if instr_m:
        data.patient_instructions = instr_m.group(1).strip()

    phys_m = re.search(r"Prescribing Physician:\s*(.+)", text)
    if phys_m:
        data.physician = phys_m.group(1).strip()

    dates = re.findall(r"\bDate:\s*(\d{4}-\d{2}-\d{2})", text)
    data.physician_date = dates[-1] if dates else ""

    return data


# ── markdown renderer ─────────────────────────────────────────────────────────

def _render(data: _RxData, layout: str) -> str:
    out: list[str] = []

    out += [f"# Prescription (Rx)", ""]

    if data.hospital:
        out += [f"**Hospital:** {data.hospital}  ", f"**Address:** {data.address}", ""]

    out += [
        "## Patient Information",
        "",
        "| Field | Value |",
        "|-------|-------|",
        f"| Name | {data.patient_name} |",
        f"| Age | {data.patient_age} |",
        f"| Date | {data.date} |",
        f"| MRN | {data.mrn} |",
        f"| Diagnosis | {data.diagnosis} |",
        "",
    ]

    if data.medications:
        out += ["## Prescribed Medications", ""]
        if layout == "A":
            out += [
                "| Medication | Dosage | Frequency |",
                "|-----------|--------|-----------|",
            ]
            for med in data.medications:
                out.append(f"| {med.name} | {med.dosage} | {med.frequency} |")
        else:
            for i, med in enumerate(data.medications, 1):
                if med.full_text:
                    out.append(f"{i}. {med.full_text}")
                else:
                    parts = [med.name]
                    if med.dosage:
                        parts.append(f"Dosage: {med.dosage}")
                    if med.frequency:
                        parts.append(f"Frequency: {med.frequency}")
                    out.append(f"{i}. " + " — ".join(parts))
        out.append("")

    if data.medication_notes:
        out += [f"> {data.medication_notes}", ""]

    if data.patient_instructions:
        out += ["## Patient Instructions", "", data.patient_instructions, ""]

    if data.physician:
        out += [
            "## Prescribing Physician",
            "",
            f"**Physician:** {data.physician}  ",
            f"**Date:** {data.physician_date}",
        ]

    return "\n".join(out)


# ── public API ────────────────────────────────────────────────────────────────

def is_prescription(text: str) -> bool:
    return "Prescription (Rx)" in text


def convert_prescription_to_markdown(text: str) -> str:
    """Convert raw extracted prescription text to structured Markdown."""
    # Detect hospital/address from first two non-empty lines for artifact stripping
    lines = [l for l in text.splitlines() if l.strip()]
    hospital = lines[0] if lines else ""
    address  = lines[1] if len(lines) > 1 else ""

    text = _strip_page_artifacts(text, hospital, address)

    if "Prescribed Medications:" in text:
        data = _parse_layout_a(text)
        return _render(data, "A")
    else:
        data = _parse_layout_b(text)
        return _render(data, "B")
