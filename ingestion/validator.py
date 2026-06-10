from __future__ import annotations
import logging
from pathlib import Path
from typing import Tuple
from app.config import settings

logger = logging.getLogger(__name__)

# Extensions accepted by the bulk (and future single-file) ingest endpoint.
SUPPORTED_EXTENSIONS: frozenset[str] = frozenset({".pdf", ".txt", ".text", ".dcm"})

_DICOM_PREAMBLE_LEN = 128
_DICOM_MAGIC = b"DICM"

# Executable magic bytes to reject
_DANGEROUS_HEADERS: list[bytes] = [
    b"MZ",           # PE/EXE
    b"\x7fELF",      # ELF
    b"#!/",          # shebang
]

_PDF_MAGIC = b"%PDF"


def _detect_mime(data: bytes) -> str:
    if data[:4] == _PDF_MAGIC:
        return "application/pdf"
    try:
        data[:512].decode("utf-8")
        return "text/plain"
    except UnicodeDecodeError:
        return "application/octet-stream"


class DocumentValidator:
    """Validate in-memory file bytes for the bulk ingest path.

    Returns (is_valid, reason). Never raises — callers rely on the return
    value to keep per-file failure from blocking the rest of the batch.
    """

    def validate(self, filename: str, content: bytes) -> Tuple[bool, str]:
        ext = Path(filename).suffix.lower()
        if ext not in SUPPORTED_EXTENSIONS:
            return False, f"Unsupported file type: {ext!r}"

        if len(content) == 0:
            return False, "File is empty"

        max_bytes = settings.max_file_size_bytes
        if len(content) > max_bytes:
            mb = max_bytes // (1024 * 1024)
            return False, f"File exceeds {mb} MB limit"

        for dangerous in _DANGEROUS_HEADERS:
            if content[:len(dangerous)] == dangerous:
                return False, "Executable/malicious file type rejected"

        if ext == ".dcm":
            if len(content) < _DICOM_PREAMBLE_LEN + 4:
                return False, "File too small to be a valid DICOM"
            if content[_DICOM_PREAMBLE_LEN:_DICOM_PREAMBLE_LEN + 4] != _DICOM_MAGIC:
                return False, "DICOM preamble magic bytes not found"

        return True, ""


def validate_file(file_path: str | Path) -> Tuple[bool, str]:
    """
    Returns (is_valid, reason).
    reason is empty string on success.
    """
    path = Path(file_path)

    if not path.exists():
        return False, "File does not exist"

    size = path.stat().st_size
    if size == 0:
        return False, "File is empty"
    if size > settings.max_file_size_bytes:
        mb = settings.max_file_size_bytes // (1024 * 1024)
        return False, f"File exceeds {mb} MB limit"

    with open(path, "rb") as f:
        header = f.read(512)

    for dangerous in _DANGEROUS_HEADERS:
        if header.startswith(dangerous):
            return False, "Executable/malicious file type rejected"

    detected_mime = _detect_mime(header)
    if detected_mime not in settings.allowed_mime_types:
        return False, f"MIME type {detected_mime!r} not allowed"

    return True, ""
