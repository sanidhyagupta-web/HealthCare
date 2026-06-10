from __future__ import annotations
import logging
from pathlib import Path
from ingestion.parsers.pdf_parser import ParsedDocument, ParsedPage

logger = logging.getLogger(__name__)


def parse_text_file(file_path: str | Path, doc_id: str) -> ParsedDocument:
    path = Path(file_path)
    with open(path, encoding="utf-8", errors="replace") as f:
        content = f.read()

    result = ParsedDocument(doc_id=doc_id)
    result.pages.append(ParsedPage(page_number=1, text=content.strip()))
    logger.info("Parsed text file %s (%d chars)", doc_id, len(content))
    return result
