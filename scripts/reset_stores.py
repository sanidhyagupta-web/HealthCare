"""
Reset all data stores — Chroma, BM25, PII indexes, SQLite registry, redacted chunks.

Usage:
    python scripts/reset_stores.py           # clears everything, keeps raw source files
    python scripts/reset_stores.py --raw     # also deletes raw source files in data/raw/
"""
import argparse
import json
import logging
import shutil
import sys
from pathlib import Path

# Add project root to path so imports work when run directly
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.config import settings
from db.database import engine
from db.models import Base, DocumentRegistry, ChunkRegistry
from sqlalchemy.orm import sessionmaker

logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(message)s")
log = logging.getLogger(__name__)


def reset_chroma() -> None:
    try:
        import chromadb
        client = chromadb.PersistentClient(path=str(settings.chroma_dir))
        try:
            client.delete_collection(settings.chroma_collection_name)
            log.info("Chroma: deleted collection '%s'", settings.chroma_collection_name)
        except Exception:
            log.info("Chroma: collection '%s' did not exist", settings.chroma_collection_name)
        client.get_or_create_collection(
            name=settings.chroma_collection_name,
            metadata={"hnsw:space": "cosine"},
        )
        log.info("Chroma: recreated empty collection")
    except ImportError:
        log.warning("chromadb not installed — skipping Chroma reset")


def reset_bm25() -> None:
    index_file = settings.data_dir / "bm25_index.json"
    index_file.write_text(json.dumps([]), encoding="utf-8")
    log.info("BM25: cleared %s", index_file)


def reset_pii_indexes() -> None:
    entity_file = settings.data_dir / "pii_entity_index.json"
    doc_file    = settings.data_dir / "pii_doc_index.json"
    entity_file.write_text(json.dumps({}), encoding="utf-8")
    doc_file.write_text(json.dumps({"doc_chunks": {}, "chunk_doc": {}}), encoding="utf-8")
    log.info("PII indexes: cleared %s and %s", entity_file.name, doc_file.name)


def reset_sqlite() -> None:
    Session = sessionmaker(bind=engine)
    session = Session()
    try:
        deleted_chunks = session.query(ChunkRegistry).delete()
        deleted_docs   = session.query(DocumentRegistry).delete()
        session.commit()
        log.info("SQLite: removed %d chunk rows, %d document rows", deleted_chunks, deleted_docs)
        log.info("SQLite: audit_log preserved")
    except Exception as exc:
        session.rollback()
        log.error("SQLite reset failed: %s", exc)
        raise
    finally:
        session.close()


def reset_redacted_chunks() -> None:
    redacted_dir = settings.processed_dir / "redacted"
    if redacted_dir.exists():
        shutil.rmtree(redacted_dir)
        redacted_dir.mkdir(parents=True)
        log.info("Processed: cleared %s", redacted_dir)
    else:
        log.info("Processed: redacted dir did not exist, nothing to clear")


def reset_raw_files() -> None:
    if settings.raw_dir.exists():
        shutil.rmtree(settings.raw_dir)
        settings.raw_dir.mkdir(parents=True)
        log.info("Raw: cleared %s", settings.raw_dir)
    else:
        log.info("Raw: directory did not exist")


def main() -> None:
    parser = argparse.ArgumentParser(description="Reset all healthcare pipeline data stores")
    parser.add_argument(
        "--raw",
        action="store_true",
        help="Also delete raw source files in data/raw/ (source documents)",
    )
    args = parser.parse_args()

    log.info("=== Resetting all stores ===")
    reset_chroma()
    reset_bm25()
    reset_pii_indexes()
    reset_sqlite()
    reset_redacted_chunks()

    if args.raw:
        reset_raw_files()
    else:
        log.info("Raw source files kept (pass --raw to delete them too)")

    log.info("=== Done — all stores empty ===")


if __name__ == "__main__":
    main()
