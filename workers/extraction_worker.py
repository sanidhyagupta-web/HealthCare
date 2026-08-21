"""
Extraction Worker
Reads redacted chunks → calls the MLX ADE API (port 8001) per sentence →
enriches chunk metadata with extracted_drugs / extracted_ades (flat strings,
Chroma-compatible) → re-serialises → pushes to embedding + keyword queues.

The MLX model is owned by the separate uvicorn process (llm/ade_api.py).
This worker is a lightweight HTTP client — no model weights loaded here.
"""
from __future__ import annotations

import json
import logging
import os
from pathlib import Path

import requests
import spacy

from ingestion.registry import update_status
from ingestion.state_machine import DocStatus
from workers.base_worker import BaseWorker
import queues

logger = logging.getLogger(__name__)

_ADE_API_URL = os.getenv("ADE_API_URL", "http://localhost:8001")

# Load spaCy once at import time — en_core_web_lg is already installed for PII detection.
# sentencizer handles medical abbreviations (Tab., Cap., Dr.) that break naive regex.
try:
    _nlp = spacy.load("en_core_web_lg", disable=["ner", "lemmatizer", "attribute_ruler"])
except OSError:
    _nlp = spacy.blank("en")
    _nlp.add_pipe("sentencizer")


def _sentences(text: str) -> list[str]:
    doc = _nlp(text.strip())
    sents = [s.text.strip() for s in doc.sents if len(s.text.strip()) > 4]

    # If spaCy sees the whole chunk as one sentence (common for line-structured
    # medical records with no terminal punctuation), fall back to line splitting.
    if len(sents) <= 1:
        sents = [ln.strip() for ln in text.splitlines() if len(ln.strip()) > 4]

    return sents


def _call_ade_api(sentence: str) -> tuple[str | None, str | None]:
    """POST one sentence to the MLX ADE API. Returns (drug, adverse_effect) or (None, None)."""
    try:
        resp = requests.post(
            f"{_ADE_API_URL}/extract",
            json={"sentence": sentence},
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
        return data.get("drug"), data.get("adverse_effect")
    except requests.exceptions.ConnectionError:
        logger.warning("ADE API unavailable at %s — skipping extraction for this sentence", _ADE_API_URL)
        return None, None
    except Exception as exc:
        logger.warning("ADE API error: %s", exc)
        return None, None


def _extract_from_chunk(chunk_text: str) -> tuple[str, str]:
    """Return (comma-joined drugs, comma-joined ades) found in chunk_text."""
    sentences = _sentences(chunk_text) or [chunk_text[:512]]
    drugs: set[str] = set()
    ades: set[str] = set()

    for sent in sentences:
        drug, ade = _call_ade_api(sent)
        if drug and drug.strip().lower() not in ("none", "null", ""):
            drugs.add(drug.strip().lower())
        if ade and ade.strip().lower() not in ("none", "null", ""):
            ades.add(ade.strip().lower())

    return ", ".join(sorted(drugs)), ", ".join(sorted(ades))


class ExtractionWorker(BaseWorker):
    def __init__(self):
        super().__init__("ExtractionWorker", queues.extraction_queue)

    def process(self, message: dict) -> None:
        doc_id = message["doc_id"]
        redacted_path = Path(message["redacted_path"])

        chunks = json.loads(redacted_path.read_text(encoding="utf-8"))

        for chunk in chunks:
            extracted_drugs, extracted_ades = _extract_from_chunk(chunk["text"])
            chunk["metadata"]["extracted_drugs"] = extracted_drugs
            chunk["metadata"]["extracted_ades"]  = extracted_ades

        redacted_path.write_text(json.dumps(chunks, indent=2), encoding="utf-8")

        update_status(doc_id, DocStatus.EXTRACTED)
        logger.info("Extraction complete for %s (%d chunks)", doc_id, len(chunks))

        queues.embedding_queue.put(message)
        queues.keyword_queue.put(message)
