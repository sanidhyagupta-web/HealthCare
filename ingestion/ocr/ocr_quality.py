import re
import logging
import requests
from ingestion.ocr.tesseract_ocr import OcrResult
from app.config import settings

logger = logging.getLogger(__name__)

_SAPLING_ENDPOINT = "https://api.sapling.ai/api/v1/medical-spellcheck"

# Regex fallback for when the API is unavailable
_CORRECTIONS: dict[str, str] = {
    "fibrilatoin": "fibrillation",
    "fibrilaton": "fibrillation",
    "arrythmia": "arrhythmia",
    "arrhytmia": "arrhythmia",
    "diabetis": "diabetes",
    "hypertenshun": "hypertension",
    "myocardail": "myocardial",
    "pneumona": "pneumonia",
    "tachycarida": "tachycardia",
    "bradycarida": "bradycardia",
}


def is_quality_sufficient(result: OcrResult) -> bool:
    if result.avg_confidence < settings.ocr_confidence_threshold:
        logger.warning(
            "OCR quality too low for %s: %.2f < %.2f",
            result.doc_id, result.avg_confidence, settings.ocr_confidence_threshold,
        )
        return False
    return True


def correct_medical_terms(text: str) -> str:
    if settings.sapling_api_key:
        try:
            resp = requests.post(
                _SAPLING_ENDPOINT,
                json={
                    "key": settings.sapling_api_key,
                    "text": text,
                    "session_id": "ocr-correction",
                },
                timeout=10,
            )
            resp.raise_for_status()
            edits = resp.json().get("edits", [])

            # Apply edits in reverse order so offsets stay valid
            edits_sorted = sorted(edits, key=lambda e: e["start"], reverse=True)
            corrected = text
            for edit in edits_sorted:
                start = edit["start"]
                end = edit["end"]
                replacement = edit["replacement"]
                corrected = corrected[:start] + replacement + corrected[end:]

            if edits:
                logger.debug("Sapling corrected %d term(s) in OCR text", len(edits))
            return corrected

        except requests.RequestException as exc:
            logger.warning("Sapling API unavailable (%s); falling back to regex", exc)

    # Regex fallback
    for wrong, right in _CORRECTIONS.items():
        text = re.sub(rf"\b{re.escape(wrong)}\b", right, text, flags=re.IGNORECASE)
    return text
