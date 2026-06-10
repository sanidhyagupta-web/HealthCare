"""
Keyword Indexing Worker
Reads redacted chunks → indexes in BM25/OpenSearch.
"""
import json
import logging
from workers.base_worker import BaseWorker
from indexing.opensearch_index import index_chunk
import queues

logger = logging.getLogger(__name__)


class KeywordIndexWorker(BaseWorker):
    def __init__(self):
        super().__init__("KeywordIndexWorker", queues.keyword_queue)

    def process(self, message: dict) -> None:
        doc_id = message["doc_id"]
        redacted_path = message["redacted_path"]

        chunks = json.loads(open(redacted_path, encoding="utf-8").read())
        for chunk in chunks:
            index_chunk(
                chunk_id=chunk["chunk_id"],
                text=chunk["text"],
                metadata=chunk["metadata"],
            )

        logger.info("Keyword-indexed %d chunks for doc %s", len(chunks), doc_id)
