"""
run.py — Starts all pipeline workers then seeds mock records and waits.

Usage:
  python run.py             # start workers + seed 20 records
  python run.py --seed 50   # seed 50 records
  python run.py --workers   # workers only, no seeding
"""
import argparse
import logging
import signal
import sys
import time
from pathlib import Path

from db.database import init_db
from workers.parser_worker import ParserWorker
from workers.markdown_worker import MarkdownWorker
from workers.chunking_worker import ChunkingWorker
from workers.pii_worker import PiiWorker
from workers.extraction_worker import ExtractionWorker
from workers.embedding_worker import EmbeddingWorker
from workers.keyword_index_worker import KeywordIndexWorker

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(name)-25s %(levelname)s %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("logs/ingestion.log"),
    ],
)
logger = logging.getLogger("run")


def recover_stuck_docs() -> None:
    """Re-enqueue documents that were in-flight when the pipeline last stopped.

    In-memory queues are lost on restart. Any doc whose SQLite status shows
    work was done but not finished needs to be pushed back into the right queue
    so it can complete without requiring a re-upload.
    """
    from db.database import engine
    from sqlalchemy.orm import sessionmaker
    from db.models import DocumentRegistry
    from app.config import settings
    import queues

    # Map each recoverable status to the queue it should be re-pushed into,
    # and which fields the downstream worker expects in the message.
    Session = sessionmaker(bind=engine)
    session = Session()
    try:
        stuck = session.query(DocumentRegistry).filter(
            DocumentRegistry.status.in_([
                "PII_PROCESSED",
                "EXTRACTED",
            ])
        ).all()

        if not stuck:
            return

        logger.info("Recovery: found %d stuck document(s) — re-queuing", len(stuck))

        for doc in stuck:
            redacted_path = (
                settings.processed_dir / "redacted" / doc.doc_id / "redacted_chunks.json"
            )
            if not redacted_path.exists():
                logger.warning("Recovery: skipping %s — redacted file missing", doc.doc_id)
                continue

            msg = {
                "doc_id":            doc.doc_id,
                "original_filename": doc.original_filename,
                "raw_s3_key":        doc.raw_path or "",
                "uploader_id":       doc.uploader_id or "system",
                "redacted_path":     str(redacted_path),
            }

            if doc.status == "PII_PROCESSED":
                queues.extraction_queue.put(msg)
                logger.info("Recovery: re-queued %s -> extraction_queue", doc.doc_id)
            elif doc.status == "EXTRACTED":
                queues.embedding_queue.put(msg)
                queues.keyword_queue.put(msg)
                logger.info("Recovery: re-queued %s -> embedding + keyword queues", doc.doc_id)

    finally:
        session.close()


def main():
    parser = argparse.ArgumentParser(description="Healthcare Semantic Search — Ingestion Pipeline")
    parser.add_argument("--seed", type=int, default=20, help="Number of mock records to seed (0 = skip)")
    parser.add_argument("--workers", action="store_true", help="Start workers only, skip seeding")
    args = parser.parse_args()

    logger.info("Initialising database...")
    init_db()

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
    logger.info("All %d pipeline workers running", len(workers))

    recover_stuck_docs()

    if not args.workers and args.seed > 0:
        logger.info("Seeding %d mock records (workers will process them)...", args.seed)
        # Import here so workers are running before we enqueue
        from scripts.seed_mock_records import seed
        seed(args.seed)

    def _shutdown(sig, frame):
        logger.info("Received shutdown signal — stopping workers")
        for w in workers:
            w.stop()
        logger.info("All workers stopped. Goodbye.")
        sys.exit(0)

    signal.signal(signal.SIGINT, _shutdown)
    signal.signal(signal.SIGTERM, _shutdown)

    logger.info("Pipeline running. Press Ctrl+C to stop.")
    try:
        while True:
            time.sleep(2)
    except KeyboardInterrupt:
        _shutdown(None, None)


if __name__ == "__main__":
    main()
