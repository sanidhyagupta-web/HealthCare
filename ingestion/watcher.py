"""
File system watcher for the raw/ directory.
Monitors for new files and enqueues them automatically.
Uses polling (no watchdog dependency required).
"""
import time
import logging
from pathlib import Path
from app.main import ingest_document
from app.config import settings

logger = logging.getLogger(__name__)

_seen: set[Path] = set()


def watch(interval: float = 5.0, uploader_id: str = "watcher") -> None:
    """Poll raw subdirectories for new files and ingest them."""
    watch_dirs = [
        settings.raw_dir / "pdfs",
        settings.raw_dir / "scanned",
        settings.raw_dir / "text",
    ]
    for d in watch_dirs:
        d.mkdir(parents=True, exist_ok=True)

    logger.info("Watching %d directories for new files (interval=%ss)", len(watch_dirs), interval)
    while True:
        for directory in watch_dirs:
            for path in directory.iterdir():
                if path.is_file() and path not in _seen:
                    _seen.add(path)
                    try:
                        doc_id = ingest_document(path, uploader_id=uploader_id)
                        logger.info("Auto-ingested %s → doc_id=%s", path.name, doc_id)
                    except ValueError as exc:
                        logger.warning("Rejected %s: %s", path.name, exc)
        time.sleep(interval)
