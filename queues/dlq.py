from __future__ import annotations
import json
import logging
from datetime import datetime
from app.config import settings

logger = logging.getLogger(__name__)

DLQ_LOG = settings.logs_dir / "dlq.log"


class DeadLetterQueue:
    """Persists failed messages to dlq.log and provides a review interface."""

    def __init__(self):
        DLQ_LOG.parent.mkdir(parents=True, exist_ok=True)

    def put(self, message: dict) -> None:
        message["dlq_timestamp"] = datetime.utcnow().isoformat()
        with open(DLQ_LOG, "a") as f:
            f.write(json.dumps(message) + "\n")
        logger.error(
            "DLQ: doc_id=%s source=%s reason=%s",
            message.get("doc_id"),
            message.get("dlq_source"),
            message.get("dlq_reason"),
        )

    def list_messages(self) -> list[dict]:
        if not DLQ_LOG.exists():
            return []
        messages = []
        with open(DLQ_LOG) as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        messages.append(json.loads(line))
                    except json.JSONDecodeError:
                        pass
        return messages
