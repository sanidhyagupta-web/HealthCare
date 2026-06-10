"""Start all pipeline workers and keep them running."""
import logging
import signal
import sys
import time
from pathlib import Path

from db.database import init_db, get_db
from db.models import DocumentRegistry
from ingestion.state_machine import DocStatus
from app.config import settings
from workers.parser_worker import ParserWorker
from workers.markdown_worker import MarkdownWorker
from workers.chunking_worker import ChunkingWorker
from workers.pii_worker import PiiWorker
from workers.extraction_worker import ExtractionWorker
from workers.embedding_worker import EmbeddingWorker
from workers.keyword_index_worker import KeywordIndexWorker
import queues

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(name)s %(levelname)s %(message)s",
)
logger = logging.getLogger(__name__)

# States whose recovery payload can be reconstructed from disk after a restart.
# Maps status -> queue to re-enqueue into.
_RECOVERABLE: dict[DocStatus, object] = {
    DocStatus.PII_PROCESSED: queues.extraction_queue,
}


def _recover_stuck_docs() -> None:
    """Re-enqueue docs whose in-memory queue message was lost on restart."""
    with get_db() as db:
        stuck = (
            db.query(DocumentRegistry)
            .filter(DocumentRegistry.status.in_([s.value for s in _RECOVERABLE]))
            .all()
        )

    if not stuck:
        return

    logger.warning("Found %d doc(s) stuck in a recoverable state — re-enqueuing", len(stuck))
    for doc in stuck:
        target_queue = _RECOVERABLE[DocStatus(doc.status)]
        redacted_path = settings.processed_dir / "redacted" / doc.doc_id / "redacted_chunks.json"

        if not redacted_path.exists():
            logger.error(
                "Cannot recover doc %s (%s): redacted file missing at %s",
                doc.doc_id, doc.status, redacted_path,
            )
            continue

        payload = {
            "doc_id": doc.doc_id,
            "redacted_path": str(redacted_path),
            "original_filename": doc.original_filename,
            "uploader_id": doc.uploader_id or "system",
        }
        target_queue.put(payload)
        logger.info("Re-enqueued doc %s (%s) -> %s", doc.doc_id, doc.status, target_queue.name)


def main():
    logger.info("Initialising database...")
    init_db()
    _recover_stuck_docs()

    workers = [
        ParserWorker(),
        MarkdownWorker(),
        ChunkingWorker(),
        PiiWorker(),
        ExtractionWorker(),
        EmbeddingWorker(),
        KeywordIndexWorker(),
    ]

    for w in workers:
        w.start()
    logger.info("All %d workers started", len(workers))

    def _shutdown(sig, frame):
        logger.info("Shutting down workers...")
        for w in workers:
            w.stop()
        sys.exit(0)

    signal.signal(signal.SIGINT, _shutdown)
    signal.signal(signal.SIGTERM, _shutdown)

    try:
        while True:
            time.sleep(5)
    except KeyboardInterrupt:
        _shutdown(None, None)


if __name__ == "__main__":
    main()
