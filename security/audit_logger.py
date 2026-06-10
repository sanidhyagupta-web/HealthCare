from __future__ import annotations
import json
import logging
from datetime import datetime
from pathlib import Path
from app.config import settings
from db.database import get_db
from db.models import AuditLog

logger = logging.getLogger(__name__)

_AUDIT_FILE = settings.logs_dir / "audit.log"


def _write_file(event: dict) -> None:
    _AUDIT_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(_AUDIT_FILE, "a") as f:
        f.write(json.dumps(event) + "\n")


def log_event(
    event_type: str,
    user_id: str = "system",
    doc_id: str | None = None,
    query: str | None = None,
    details: dict | None = None,
) -> None:
    event = {
        "event_type": event_type,
        "user_id": user_id,
        "doc_id": doc_id,
        "query": query,
        "details": details or {},
        "timestamp": datetime.utcnow().isoformat(),
    }

    _write_file(event)

    try:
        with get_db() as db:
            db.add(AuditLog(
                event_type=event_type,
                user_id=user_id,
                doc_id=doc_id,
                query=query,
                details=details or {},
            ))
    except Exception as exc:
        logger.warning("Failed to write audit log to DB: %s", exc)

    logger.info("AUDIT [%s] user=%s doc=%s", event_type, user_id, doc_id)


def get_audit_trail(doc_id: str | None = None, limit: int = 100) -> list[dict]:
    try:
        with get_db() as db:
            q = db.query(AuditLog)
            if doc_id:
                q = q.filter_by(doc_id=doc_id)
            rows = q.order_by(AuditLog.timestamp.desc()).limit(limit).all()
            return [
                {
                    "event_type": r.event_type,
                    "user_id": r.user_id,
                    "doc_id": r.doc_id,
                    "query": r.query,
                    "details": r.details,
                    "timestamp": r.timestamp.isoformat() if r.timestamp else None,
                }
                for r in rows
            ]
    except Exception as exc:
        logger.error("Failed to retrieve audit trail: %s", exc)
        return []
