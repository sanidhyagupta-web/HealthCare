"""
Entity-Preserving Chunker for medical documents.

Strategy
--------
1. Split text into lines and tag each line with detected medical entity types
   (medications, dosages, vital signs, lab values, ICD-10 codes, etc.).
2. Group consecutive lines that belong to the same medical concept into
   "entity groups" — these are atomic units that must never be split.
3. Greedily pack entity groups into chunks that respect `chunk_size`.
   A group may cause a chunk to slightly exceed `chunk_size`, but a group
   is never broken across two chunks.

This guarantees that clinical relationships like:
  "Tab. Augmentin 625mg"     (medication)
  "1 - 0 - 1  x 5 days"     (dosage/frequency)
  "after meals"              (instruction)
always land in the same chunk.
"""
from __future__ import annotations
import re
import uuid
import logging
from dataclasses import dataclass, field
from app.config import settings

logger = logging.getLogger(__name__)


# ── Medical entity patterns ───────────────────────────────────────────────────

_ENTITY_PATTERNS: list[tuple[str, re.Pattern]] = [
    # Patient demographic fields  e.g. "Name: John Doe", "MRN: 12345", "DOB: 01/01/1990"
    ("PATIENT_DEMOGRAPHICS", re.compile(
        r"^\s*(?:Patient\s+)?(?:Name|MRN|DOB|Date\s+of\s+Birth|Age|Sex|Gender|"
        r"Address|Phone|Insurance|Policy\s*(?:No|Number|#)|Group\s*(?:No|Number|#)|"
        r"Patient\s+ID|ID\s*(?:No|Number|#)|Allergies?)\s*:",
        re.IGNORECASE | re.MULTILINE,
    )),
    # Prescription header  e.g. "Rx,"  "R/"
    ("RX_HEADER", re.compile(
        r"^\s*R[xX]\s*[,./]?\s*$",
        re.MULTILINE,
    )),
    # Medication with form  e.g. "Tab. Augmentin 625mg", "Cap Metformin 500 mg"
    ("MEDICATION", re.compile(
        r"\b(?:Tab|Cap|Inj|Syr|Oint|Drop|Gel|Cream|Susp|Sol|IV|IM|SC|PO)\b"
        r".{0,60}?\d+\s*(?:mg|mcg|g|ml|IU|mEq|units?)\b",
        re.IGNORECASE,
    )),
    # Dosage/frequency  e.g. "1 - 0 - 1 x 5days", "1—0—0 × 5 days"
    ("DOSAGE_FREQ", re.compile(
        r"\b\d+\s*[-–—]\s*\d+\s*[-–—]\s*\d+\s*[xX×]?\s*\d+\s*"
        r"(?:days?|wks?|weeks?|months?|mo)\b",
        re.IGNORECASE,
    )),
    # Meal-time instruction  e.g. "after meals", "before meals", "with food"
    ("MEAL_INSTRUCTION", re.compile(
        r"\b(?:before|after|with)\s+(?:meals?|food|eating|dinner|lunch|breakfast)\b",
        re.IGNORECASE,
    )),
    # Duration  e.g. "x 1 week", "x 3 months", "for 7 days"
    ("DURATION", re.compile(
        r"\b(?:x|for|×)\s*\d+\s*(?:days?|wks?|weeks?|months?)\b",
        re.IGNORECASE,
    )),
    # Standalone drug dosage  e.g. "625mg", "40 mg", "5mg/kg/day"
    ("DRUG_DOSE", re.compile(
        r"\b\d+(?:\.\d+)?\s*(?:mg|mcg|g|ml|IU|mEq|mmol)\b"
        r"(?:/(?:kg|day|dose|hr|h))?\b",
        re.IGNORECASE,
    )),
    # Vital signs  e.g. "BP: 120/80 mmHg", "HR 72 bpm", "SpO2: 98%"
    ("VITAL_SIGN", re.compile(
        r"\b(?:BP|HR|Temp|RR|SpO2|O2\s*Sat|Pulse|Resp(?:iration)?|"
        r"Weight|Height|BMI|GCS)\s*[:=]?\s*[\d./]+\s*"
        r"(?:mmHg|bpm|°[CF]|%|kg|lbs|cm|m|kg/m[²2])?\b",
        re.IGNORECASE,
    )),
    # Lab values  e.g. "HbA1c: 7.2%", "Creatinine: 1.1 mg/dL"
    ("LAB_VALUE", re.compile(
        r"\b(?:HbA1c|Glucose|Creatinine|Hemoglobin|Hb|WBC|RBC|PLT|Platelets|"
        r"Sodium|Na|Potassium|K|Chloride|Cl|BUN|ALT|AST|ALP|GGT|Bilirubin|"
        r"Cholesterol|LDL|HDL|Triglycerides|eGFR|TSH|T3|T4|"
        r"INR|PT|aPTT|D-dimer|Ferritin|Folate|B12|Calcium|Ca|Phosphorus|Mg)\s*"
        r"[:=]\s*[\d.]+\s*(?:mg/dL|mmol/L|%|mEq/L|U/L|g/dL|ng/mL|IU/mL)?\b",
        re.IGNORECASE,
    )),
    # ICD-10 codes  e.g. "E11.9", "J44.1"
    ("ICD10", re.compile(r"\b[A-Z]\d{2}(?:\.\d{1,4})?\b")),
    # Advisory/instruction line  e.g. "Adv:", "Advice:", "Instructions:"
    ("ADVISORY", re.compile(
        r"^\s*(?:Adv|Advice|Instructions?|Note|Follow[- ]?up|F/U)\s*[:.]",
        re.IGNORECASE | re.MULTILINE,
    )),
]


def _tag_line(line: str) -> set[str]:
    """Return the set of entity type names present in `line`."""
    tags: set[str] = set()
    for name, pattern in _ENTITY_PATTERNS:
        if pattern.search(line):
            tags.add(name)
    return tags


def _build_entity_groups(lines: list[str]) -> list[list[str]]:
    """
    Merge consecutive lines into sticky groups so medical entities are atomic.

    Stickiness rules (applied in order):
    - A MEDICATION line sticks to the next line (likely its dosage/frequency).
    - A DOSAGE_FREQ or DRUG_DOSE line sticks to the previous line.
    - A MEAL_INSTRUCTION line sticks to adjacent medication/dosage lines.
    - A DURATION line sticks to the previous line.
    - An RX_HEADER line sticks to all following lines until a blank line.
    - A line with no tags and length < 8 chars (e.g. "1—0—0") is assumed
      to be a continuation of the previous tagged line.
    """
    if not lines:
        return []

    tags = [_tag_line(l) for l in lines]
    groups: list[list[str]] = []
    current_group: list[str] = [lines[0]]
    in_rx_block = bool("RX_HEADER" in tags[0])

    for i in range(1, len(lines)):
        line = lines[i]
        tag = tags[i]
        prev_tag = tags[i - 1]

        # Blank line terminates an Rx block and closes the current group
        if not line.strip():
            if current_group:
                groups.append(current_group)
            current_group = []
            in_rx_block = False
            continue

        sticky = (
            in_rx_block
            or bool("RX_HEADER" in tag)
            or bool("PATIENT_DEMOGRAPHICS" in prev_tag)  # demographics label → value sticky
            or bool("PATIENT_DEMOGRAPHICS" in tag)       # demographics lines cluster together
            or bool("MEDICATION" in prev_tag)            # medication → next line sticky
            or bool("DOSAGE_FREQ" in tag)                # dosage sticks back
            or bool("DRUG_DOSE" in tag and not tag - {"DRUG_DOSE"})  # bare dose line
            or bool("MEAL_INSTRUCTION" in tag)           # meal instruction sticks
            or bool("DURATION" in tag and not tag - {"DURATION"})    # bare duration
            or bool("ADVISORY" in prev_tag)              # advisory → next line sticky
            or (not tag and len(line.strip()) < 10 and current_group)  # short non-tagged
        )

        if "RX_HEADER" in tag:
            in_rx_block = True

        if sticky:
            current_group.append(line)
        else:
            if current_group:
                groups.append(current_group)
            current_group = [line]

    if current_group:
        groups.append(current_group)

    return groups


def _words(text: str) -> int:
    return len(text.split())


# ── Public interface ──────────────────────────────────────────────────────────

@dataclass
class Chunk:
    chunk_id: str
    doc_id: str
    text: str
    chunk_hash: str
    chunk_index: int
    section: str
    page_number: int
    parent_chunk_id: str | None = None
    entity_types: list[str] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)


def chunk_markdown(markdown_text: str, doc_id: str, page_number: int = 0) -> list[Chunk]:
    from ingestion.chunking.chunk_hasher import compute_hash

    # Split on ## section headers
    sections = re.split(r"(?=^## )", markdown_text, flags=re.MULTILINE)

    chunks: list[Chunk] = []
    chunk_index = 0

    for section_text in sections:
        section_text = section_text.strip()
        if not section_text:
            continue

        header_match = re.match(r"^## (.+)$", section_text, re.MULTILINE)
        section_name = header_match.group(1).strip() if header_match else "General"

        body = re.sub(r"^## .+$", "", section_text, flags=re.MULTILINE).strip()
        if not body:
            continue

        lines = body.splitlines()
        entity_groups = _build_entity_groups(lines)

        # Pack entity groups into chunks greedily
        current_lines: list[str] = []
        current_words = 0
        current_entity_types: set[str] = set()

        for group in entity_groups:
            group_text = "\n".join(group)
            group_words = _words(group_text)
            group_entities: set[str] = set()
            for ln in group:
                group_entities.update(_tag_line(ln))

            fits = (current_words + group_words) <= settings.chunk_size

            if not fits and current_lines:
                # Flush current chunk
                chunk_text = "\n".join(current_lines).strip()
                if chunk_text:
                    chunks.append(Chunk(
                        chunk_id=str(uuid.uuid4()),
                        doc_id=doc_id,
                        text=chunk_text,
                        chunk_hash=compute_hash(chunk_text),
                        chunk_index=chunk_index,
                        section=section_name,
                        page_number=page_number,
                        parent_chunk_id=None,
                        entity_types=sorted(current_entity_types),
                    ))
                    chunk_index += 1
                current_lines = []
                current_words = 0
                current_entity_types = set()

            current_lines.extend(group)
            current_words += group_words
            current_entity_types.update(group_entities)

        # Flush last chunk for this section
        if current_lines:
            chunk_text = "\n".join(current_lines).strip()
            if chunk_text:
                chunks.append(Chunk(
                    chunk_id=str(uuid.uuid4()),
                    doc_id=doc_id,
                    text=chunk_text,
                    chunk_hash=compute_hash(chunk_text),
                    chunk_index=chunk_index,
                    section=section_name,
                    page_number=page_number,
                    parent_chunk_id=None,
                    entity_types=sorted(current_entity_types),
                ))
                chunk_index += 1

    # Merge any chunk shorter than 30 words into the following chunk to avoid
    # orphaned single-line sections (e.g. a 2-line Diagnosis section standing alone).
    _MIN_CHUNK_WORDS = 30
    merged: list[Chunk] = []
    pending: Chunk | None = None
    for chunk in chunks:
        if pending is not None:
            merged_text = pending.text + "\n" + chunk.text
            merged_entities = sorted(set(pending.entity_types) | set(chunk.entity_types))
            pending = Chunk(
                chunk_id=pending.chunk_id,
                doc_id=pending.doc_id,
                text=merged_text,
                chunk_hash=compute_hash(merged_text),
                chunk_index=pending.chunk_index,
                section=pending.section,
                page_number=pending.page_number,
                parent_chunk_id=pending.parent_chunk_id,
                entity_types=merged_entities,
            )
            if _words(pending.text) >= _MIN_CHUNK_WORDS:
                merged.append(pending)
                pending = None
        else:
            if _words(chunk.text) < _MIN_CHUNK_WORDS:
                pending = chunk
            else:
                merged.append(chunk)

    if pending is not None:
        if merged:
            # Append to the last chunk instead of leaving it alone
            last = merged[-1]
            merged_text = last.text + "\n" + pending.text
            merged_entities = sorted(set(last.entity_types) | set(pending.entity_types))
            merged[-1] = Chunk(
                chunk_id=last.chunk_id,
                doc_id=last.doc_id,
                text=merged_text,
                chunk_hash=compute_hash(merged_text),
                chunk_index=last.chunk_index,
                section=last.section,
                page_number=last.page_number,
                parent_chunk_id=last.parent_chunk_id,
                entity_types=merged_entities,
            )
        else:
            merged.append(pending)

    # Re-number chunk_index sequentially after merges
    for i, c in enumerate(merged):
        c.chunk_index = i

    logger.info(
        "Entity-preserving chunked doc %s into %d chunks", doc_id, len(merged)
    )
    return merged
