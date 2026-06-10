"""Base class for all pipeline workers."""
from __future__ import annotations
import logging
import threading
from queues.queue_client import QueueClient
from app.config import settings

logger = logging.getLogger(__name__)


class BaseWorker:
    def __init__(self, name: str, input_queue: QueueClient):
        self.name = name
        self.input_queue = input_queue
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None

    def process(self, message: dict) -> None:
        raise NotImplementedError

    def run(self) -> None:
        logger.info("[%s] started", self.name)
        while not self._stop_event.is_set():
            message = self.input_queue.get(timeout=settings.worker_poll_timeout)
            if message is None:
                continue
            try:
                self.process(message)
            except Exception as exc:
                retry = message.get("retry_count", 0)
                logger.error("[%s] error processing doc %s: %s", self.name, message.get("doc_id"), exc, exc_info=True)
                if retry >= settings.max_retries:
                    self.input_queue.send_to_dlq(message, reason=str(exc))
                else:
                    message["retry_count"] = retry + 1
                    self.input_queue.put(message)
            finally:
                self.input_queue.task_done()
        logger.info("[%s] stopped", self.name)

    def start(self) -> None:
        self._thread = threading.Thread(target=self.run, name=self.name, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=5)
