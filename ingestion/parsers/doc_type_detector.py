"""
Document type detector for the Harmony ingestion pipeline.

Called by ParserWorker to decide which parser handles a given upload.
Inspects the file extension; for DICOM files optionally validates the
standard magic bytes so a misnamed file is caught before parsing begins.

Return values
-------------
"dicom"       — .dcm file (DICOM Part 10)
"pdf_typed"   — machine-readable PDF (default; ParserWorker downgrades to
                "pdf_scanned" if text density is below the OCR threshold)
"pdf_scanned" — image-only PDF, needs OCR
"text"        — plain .txt / .text file

Raises ValueError for unsupported extensions.
"""
from __future__ import annotations

from pathlib import Path

# DICOM Part 10 conformant files have the ASCII string "DICM" at bytes 128-131
# (after the 128-byte preamble).  Non-conformant DICOM files omit the preamble;
# we accept those too (pydicom handles them) but do not fail here if bytes are
# not provided.
_DICOM_MAGIC = b"DICM"
_DICOM_MAGIC_OFFSET = 128


def detect_doc_type(filename: str, file_bytes: bytes | None = None) -> str:
    """Return the document-type string for *filename*.

    Parameters
    ----------
    filename:
        Original upload filename (used for extension detection).
    file_bytes:
        Optional raw file bytes.  When provided for a .dcm file the DICOM
        magic bytes are validated so a misnamed file is rejected early.

    Raises
    ------
    ValueError
        If the extension is unsupported, or if a .dcm file's magic bytes do
        not match (and file_bytes were supplied).
    """
    ext = Path(filename).suffix.lower()

    if ext == ".dcm":
        if (
            file_bytes is not None
            and len(file_bytes) >= _DICOM_MAGIC_OFFSET + 4
            and file_bytes[_DICOM_MAGIC_OFFSET : _DICOM_MAGIC_OFFSET + 4] != _DICOM_MAGIC
        ):
            raise ValueError(
                f"{filename!r} has a .dcm extension but is missing the DICOM preamble "
                f"magic bytes at offset {_DICOM_MAGIC_OFFSET}."
            )
        return "dicom"

    if ext == ".pdf":
        # Typed-vs-scanned discrimination is deferred to ParserWorker, which
        # measures PyMuPDF text density and downgrades to "pdf_scanned" when
        # the density is below settings.ocr_confidence_threshold.
        return "pdf_typed"

    if ext in (".txt", ".text"):
        return "text"

    raise ValueError(
        f"Unsupported file extension {ext!r} in {filename!r}. "
        f"Accepted extensions: .dcm, .pdf, .txt, .text"
    )
