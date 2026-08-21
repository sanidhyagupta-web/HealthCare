"""OCR for scanned PDFs using pytesseract + pdf2image.

Two-stage strategy — Claude Vision first, Tesseract as fallback:

  1. Claude Vision (claude-sonnet-4-6): handles handwriting, spatial annotations
     (margin labels + braces), and mixed printed/handwritten layouts that
     completely defeat Tesseract. Used when ANTHROPIC_API_KEY is set.
  2. Tesseract --psm 11 (sparse text): fallback when Vision is unavailable or
     fails. --psm 11 is better than --psm 6 for scattered/handwritten layouts.

Tesseract confidence scores measure how certain Tesseract is about its own
(often wrong) readings — they do NOT measure accuracy on handwriting.
Using them as a gating threshold is unreliable, so Vision always goes first.
"""
from __future__ import annotations
import base64
import io
import logging
from pathlib import Path
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class OcrPage:
    page_number: int
    text: str
    confidence: float  # 0.0–1.0


@dataclass
class OcrResult:
    doc_id: str
    pages: list[OcrPage] = field(default_factory=list)

    @property
    def full_text(self) -> str:
        return "\n\n".join(p.text for p in self.pages if p.text.strip())

    @property
    def avg_confidence(self) -> float:
        if not self.pages:
            return 0.0
        return sum(p.confidence for p in self.pages) / len(self.pages)


def _preprocess(img):
    """Grayscale → contrast → adaptive threshold → denoise."""
    import numpy as np
    from PIL import Image, ImageEnhance, ImageFilter

    gray = img.convert("L")
    gray = ImageEnhance.Contrast(gray).enhance(2.0)
    gray = ImageEnhance.Sharpness(gray).enhance(2.0)

    arr = np.array(gray, dtype=np.uint8)
    try:
        from scipy.ndimage import uniform_filter
        local_mean = uniform_filter(arr.astype(float), size=51)
        binary = (arr > local_mean * 0.85).astype(np.uint8) * 255
        processed = Image.fromarray(binary)
    except ImportError:
        threshold = int(np.percentile(arr, 50))
        binary = np.where(arr > threshold, 255, 0).astype(np.uint8)
        processed = Image.fromarray(binary)

    return processed.filter(ImageFilter.MedianFilter(size=3))


def _compress_for_vision(img, max_bytes: int = 4 * 1024 * 1024) -> tuple[bytes, str]:
    """
    Compress a PIL image to fit within Claude Vision's 5 MB limit.
    Tries JPEG at decreasing quality, then resizes if still over limit.
    Returns (image_bytes, media_type).
    """
    from PIL import Image
    img_rgb = img.convert("RGB")
    quality = 85
    while quality >= 40:
        buf = io.BytesIO()
        img_rgb.save(buf, format="JPEG", quality=quality)
        if buf.tell() <= max_bytes:
            return buf.getvalue(), "image/jpeg"
        quality -= 15

    # Still too large — scale down proportionally
    scale = (max_bytes / buf.tell()) ** 0.5
    new_size = (int(img_rgb.width * scale), int(img_rgb.height * scale))
    img_rgb = img_rgb.resize(new_size, Image.LANCZOS)
    buf = io.BytesIO()
    img_rgb.save(buf, format="JPEG", quality=85)
    return buf.getvalue(), "image/jpeg"


def _ocr_with_claude_vision(img) -> str:
    """
    Use Claude Vision to extract text from a prescription image.
    Handles handwriting and spatial layouts (margin annotations, braces)
    that completely defeat Tesseract.
    Returns empty string if Anthropic key is not configured.
    """
    from app.config import settings
    if not settings.anthropic_api_key:
        return ""

    try:
        import anthropic

        # Compress image to stay under the 5 MB API limit before base64 encoding
        image_bytes, media_type = _compress_for_vision(img)
        image_b64 = base64.b64encode(image_bytes).decode("utf-8")
        logger.debug("Vision image: %.2f MB (%s)", len(image_bytes) / 1024 / 1024, media_type)

        client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=2048,
            messages=[{
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": media_type,
                            "data": image_b64,
                        },
                    },
                    {
                        "type": "text",
                        "text": (
                            "Transcribe every piece of text in this medical prescription image exactly as written. "
                            "Rules:\n"
                            "- Preserve the structure: patient name/date at top, Rx section, medications with "
                            "dosage and frequency, meal timing instructions (before/after meals) noted inline "
                            "with the relevant drug, advisory section at the end.\n"
                            "- For each medication write one line: "
                            "'[meal timing if any] [drug name] [dose] [frequency x duration]'\n"
                            "- Do NOT interpret or add information — only transcribe what is written.\n"
                            "- Output plain text only, no markdown."
                        ),
                    },
                ],
            }],
        )
        text = response.content[0].text.strip()
        logger.info("Claude Vision OCR returned %d chars", len(text))
        return text

    except Exception as e:
        logger.warning("Claude Vision OCR failed, keeping Tesseract output: %s", e)
        return ""


def run_ocr(file_path: str | Path, doc_id: str) -> OcrResult:
    path = Path(file_path)
    result = OcrResult(doc_id=doc_id)

    try:
        import pytesseract
        from pdf2image import convert_from_path

        pages = convert_from_path(str(path), dpi=400)

        # --psm 11 (sparse text): finds text anywhere on the page in any order.
        # Far better than --psm 6 for handwritten prescriptions with margin
        # annotations (e.g. "after meals {" on the left side of medication lines).
        tess_config = "--oem 1 --psm 11"

        for page_num, img in enumerate(pages, start=1):
            # ── Stage 1: Claude Vision (preferred for handwriting) ────────────
            vision_text = _ocr_with_claude_vision(img)
            if vision_text:
                result.pages.append(OcrPage(
                    page_number=page_num,
                    text=vision_text,
                    confidence=0.95,
                ))
                logger.info("Page %d: used Claude Vision OCR", page_num)
                continue

            # ── Stage 2: Tesseract fallback (no API key or Vision failed) ─────
            logger.info("Page %d: Claude Vision unavailable, falling back to Tesseract", page_num)
            processed = _preprocess(img)

            data = pytesseract.image_to_data(
                processed, lang="eng", config=tess_config,
                output_type=pytesseract.Output.DATAFRAME,
            )
            tess_text = pytesseract.image_to_string(
                processed, lang="eng", config=tess_config,
            )

            valid = data[data["conf"] != -1]["conf"]
            confidence = float(valid.mean()) / 100.0 if not valid.empty else 0.0

            logger.debug("Page %d: Tesseract confidence=%.2f, chars=%d",
                         page_num, confidence, len(tess_text.strip()))

            result.pages.append(OcrPage(
                page_number=page_num,
                text=tess_text.strip(),
                confidence=confidence,
            ))

        logger.info("OCR completed for %s: %d page(s), avg confidence=%.2f",
                    doc_id, len(result.pages), result.avg_confidence)

    except ImportError as e:
        logger.error("OCR dependencies missing: %s", e)
        raise RuntimeError(f"OCR dependencies not installed: {e}")

    return result
