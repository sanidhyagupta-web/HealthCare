import queue
import logging
from typing import Any, Optional
from app.config import settings

logger = logging.getLogger(__name__)


class QueueClient:
    """In-process thread-safe queue with DLQ routing on max retries exceeded."""

    def __init__(self, name: str, dlq: Optional["QueueClient"] = None):
        self.name = name
        self._q: queue.Queue = queue.Queue(maxsize=settings.queue_max_size)
        self.dlq = dlq

    def put(self, message: dict) -> None:
        self._q.put(message)
        logger.debug("[%s] enqueued doc_id=%s", self.name, message.get("doc_id"))

    def get(self, timeout: float = None) -> Optional[dict]:
        t = timeout if timeout is not None else settings.worker_poll_timeout
        try:
            return self._q.get(timeout=t)
        except queue.Empty:
            return None

    def task_done(self) -> None:
        self._q.task_done()

    def send_to_dlq(self, message: dict, reason: str) -> None:
        if self.dlq is None:
            logger.error("[%s] No DLQ configured; dropping message %s", self.name, message.get("doc_id"))
            return
        message["dlq_reason"] = reason
        message["dlq_source"] = self.name
        self.dlq.put(message)
        logger.warning("[%s] Sent to DLQ: doc_id=%s reason=%s", self.name, message.get("doc_id"), reason)

    def qsize(self) -> int:
        return self._q.qsize()

    def __repr__(self) -> str:
        return f"QueueClient(name={self.name!r}, size={self.qsize()})"
