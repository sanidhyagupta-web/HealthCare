"""Parse selectable-text PDFs using PyMuPDF."""
from __future__ import annotations
import logging
from pathlib import Path
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class ParsedPage:
    page_number: int
    text: str
    tables: list[str] = field(default_factory=list)


@dataclass
class ParsedDocument:
    doc_id: str
    pages: list[ParsedPage] = field(default_factory=list)

    @property
    def full_text(self) -> str:
        return "\n\n".join(p.text for p in self.pages if p.text.strip())


def parse_typed_pdf(file_path: str | Path, doc_id: str) -> ParsedDocument:
    path = Path(file_path)
    result = ParsedDocument(doc_id=doc_id)

    try:
        import fitz

        doc = fitz.open(str(path))
        for page_num, page in enumerate(doc, start=1):
            text = page.get_text("text")
            result.pages.append(ParsedPage(
                page_number=page_num,
                text=text.strip(),
            ))
        doc.close()
        logger.info("Parsed typed PDF %s: %d pages", doc_id, len(result.pages))

    except ImportError:
        logger.error("PyMuPDF not installed. Cannot parse typed PDF %s", doc_id)
        raise RuntimeError("PyMuPDF (fitz) is required. Install: pip install pymupdf")

    return result
