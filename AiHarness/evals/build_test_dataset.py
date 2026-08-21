"""
Build a test dataset for drug-ADE extraction from medical records in Dataset/.

For each PDF:
  1. Extract full text with PyMuPDF.
  2. Split into sentences.
  3. Ask Claude to label any sentence that contains a drug name and an adverse
     effect with {sentence, drug, adverse_effect}.
  4. Write to AiHarness/evals/test_dataset.jsonl
"""
from __future__ import annotations

import json
import os
import re
import sys
import glob
from pathlib import Path

import fitz  # PyMuPDF

# ── Paths ─────────────────────────────────────────────────────────────────────
ROOT = Path(__file__).resolve().parents[2]
DATASET_DIR = ROOT / "Dataset"
OUTPUT_PATH = Path(__file__).parent / "test_dataset.jsonl"

# ── Claude setup ──────────────────────────────────────────────────────────────
from dotenv import load_dotenv
load_dotenv(ROOT / ".env")
import anthropic

client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

LABEL_SYSTEM = """You are a clinical pharmacovigilance expert labelling a training dataset.

You are given the FULL TEXT of a single prescription document.

Your task:
1. Identify every drug mentioned in the prescription (any drug, brand or generic).
2. For each drug, find any sentence (or closely linked instruction line) in this document
   that associates that drug with a side effect, adverse event, or risk.
   - A sentence may name the drug explicitly ("Take sertraline with food to avoid
     gastrointestinal side effects") OR the drug may be clear from a numbered/bulleted
     instruction block that starts with the drug name.
3. For each qualifying (sentence, drug, adverse_effect) triple, return a JSON object:
     "sentence"       – a single sentence that MUST contain the drug name explicitly.
                        If the source sentence is a generic warning ("Be aware of side
                        effects such as X") without naming the drug, rewrite it to
                        embed the generic drug name: e.g.
                        "Sertraline may cause gastrointestinal side effects."
                        Keep rewrites concise and clinically accurate.
     "drug"           – generic drug name, all-lowercase (e.g. "sertraline")
     "adverse_effect" – the specific side effect or adverse effect, all-lowercase, brief
                        (e.g. "gastrointestinal side effects", "drowsiness", "oral thrush")

Return a JSON array of these objects. If a document has no drug-ADE sentences return [].
Do NOT fabricate; only use what is explicitly stated. One entry per (drug, adverse_effect) pair."""


def extract_text(pdf_path: str) -> str:
    doc = fitz.open(pdf_path)
    return "\n".join(page.get_text() for page in doc)


def label_document(text: str) -> list[dict]:
    """Pass the full document text to Claude; return labelled drug-ADE pairs."""
    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=4096,
        system=LABEL_SYSTEM,
        messages=[{"role": "user", "content": f"DOCUMENT TEXT:\n\n{text}"}],
    )
    raw = response.content[0].text.strip()
    raw = re.sub(r"^```(?:json)?\n?", "", raw)
    raw = re.sub(r"\n?```$", "", raw)
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, ValueError):
        return []


def main() -> None:
    pdfs = sorted(glob.glob(str(DATASET_DIR / "**/*.pdf"), recursive=True))
    print(f"Found {len(pdfs)} PDFs in {DATASET_DIR}")

    records: list[dict] = []
    seen_sentences: set[str] = set()

    for pdf_path in pdfs:
        fname = Path(pdf_path).name
        # Skip handwritten PDFs — OCR text is unreliable
        if "HandWritten" in fname:
            print(f"  Skipping {fname} (handwritten)")
            continue

        print(f"  Processing {fname} ...", end=" ", flush=True)
        text = extract_text(pdf_path)
        pairs = label_document(text)
        new_this_file = 0
        for pair in pairs:
            s = pair.get("sentence", "").strip()
            drug = pair.get("drug", "").lower().strip()
            ade = pair.get("adverse_effect", "").lower().strip()
            if not s or not drug or not ade:
                continue
            # Drop rows where the drug name doesn't appear in the sentence —
            # the model cannot extract what isn't there.
            # Use the first token of the drug name for compound names like
            # "fluticasone/salmeterol".
            primary_drug = re.split(r"[/\s]", drug)[0]
            if primary_drug not in s.lower():
                continue
            # Normalise key to avoid near-duplicates from different source files
            key = s.lower()
            if key in seen_sentences:
                continue
            seen_sentences.add(key)
            records.append(
                {
                    "sentence": s,
                    "drug": pair.get("drug", "").lower().strip(),
                    "adverse_effect": pair.get("adverse_effect", "").lower().strip(),
                    "source_file": fname,
                }
            )
            new_this_file += 1
        print(f"+{new_this_file} pairs (total: {len(records)})")

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT_PATH.open("w") as f:
        for rec in records:
            f.write(json.dumps(rec) + "\n")

    print(f"\nDataset written to {OUTPUT_PATH} ({len(records)} rows)")


if __name__ == "__main__":
    main()
