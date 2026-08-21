from queues.dlq import DeadLetterQueue
from queues.queue_client import QueueClient

_dlq_instance = DeadLetterQueue()


def make_queue(name: str) -> QueueClient:
    return QueueClient(name=name, dlq=_dlq_instance)


parsing_queue = make_queue("parsing_queue")
markdown_queue = make_queue("markdown_queue")
chunking_queue = make_queue("chunking_queue")
pii_queue = make_queue("pii_queue")
extraction_queue = make_queue("extraction_queue")
embedding_queue = make_queue("embedding_queue")
keyword_queue = make_queue("keyword_queue")
dlq = _dlq_instance
