"""
Markdown Worker (Nugget)
Downloads parsed text from S3 → converts to structured markdown →
uploads markdown back to S3 → pushes to chunking_queue.
"""
from __future__ import annotations
import logging
from workers.base_worker import BaseWorker
from ingestion.markdown.markdown_converter import convert_to_markdown
from ingestion.registry import update_status
from ingestion.state_machine import DocStatus
from storage.s3_client import download_bytes, upload
import queues

logger = logging.getLogger(__name__)


class MarkdownWorker(BaseWorker):
    def __init__(self):
        super().__init__("MarkdownWorker", queues.markdown_queue)

    def process(self, message: dict) -> None:
        doc_id = message["doc_id"]
        parsed_s3_key = message["parsed_s3_key"]

        raw_text = download_bytes(parsed_s3_key).decode("utf-8")
        markdown = convert_to_markdown(raw_text, doc_id=doc_id)

        # Upload structured markdown to S3 (still contains PII — chunking happens next)
        markdown_s3_key = f"processed/{doc_id}/markdown.md"
        upload(markdown_s3_key, markdown)

        update_status(doc_id, DocStatus.MARKDOWN_READY)

        queues.chunking_queue.put({
            **message,
            "markdown_s3_key": markdown_s3_key,
        })
        logger.info("Markdown uploaded to S3 for %s (%d chars)", doc_id, len(markdown))
