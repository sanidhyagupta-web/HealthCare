import os
from pathlib import Path
from dataclasses import dataclass, field
from dotenv import load_dotenv

BASE_DIR = Path(__file__).parent.parent
load_dotenv(BASE_DIR / ".env")


@dataclass
class Settings:
    base_dir: Path = BASE_DIR
    data_dir: Path = BASE_DIR / "data"
    raw_dir: Path = BASE_DIR / "data" / "raw"
    processed_dir: Path = BASE_DIR / "data" / "processed"
    failed_dir: Path = BASE_DIR / "data" / "failed"
    logs_dir: Path = BASE_DIR / "logs"
    chroma_dir: Path = BASE_DIR / "data" / "chroma"

    db_path: str = str(BASE_DIR / "db" / "healthcare_registry.db")

    queue_max_size: int = 500
    worker_poll_timeout: float = 1.0
    max_retries: int = 3

    allowed_mime_types: list = field(default_factory=lambda: [
        "application/pdf",
        "text/plain",
    ])
    max_file_size_bytes: int = 50 * 1024 * 1024  # 50 MB

    ocr_confidence_threshold: float = float(os.getenv("OCR_CONFIDENCE_THRESHOLD", "0.40"))

    chunk_size: int = 500
    chunk_overlap: int = 50

    qlora_adapter_path: Path = BASE_DIR / "qlora-adapter-happy-sweep-1_v0"

    embedding_model: str = os.getenv("EMBEDDING_MODEL", "all-MiniLM-L6-v2")
    embedding_batch_size: int = 32

    chroma_collection_name: str = "healthcare_docs"

    encryption_key: str = os.getenv("ENCRYPTION_KEY", "")

    sapling_api_key: str = os.getenv("SAPLING_API_KEY", "")
    anthropic_api_key: str = os.getenv("ANTHROPIC_API_KEY", "")

    # AWS S3 + KMS — required for raw/markdown storage in production
    aws_region: str = os.getenv("AWS_REGION", "us-east-1")
    s3_bucket: str = os.getenv("S3_BUCKET", "")
    kms_key_id: str = os.getenv("KMS_KEY_ID", "")   # ARN or alias; blank = SSE-S3 fallback
    aws_access_key_id: str = os.getenv("AWS_ACCESS_KEY_ID", "")
    aws_secret_access_key: str = os.getenv("AWS_SECRET_ACCESS_KEY", "")
    aws_session_token: str = os.getenv("AWS_SESSION_TOKEN", "")

    rate_limit_per_minute: int = 10

    log_level: str = os.getenv("LOG_LEVEL", "INFO")


settings = Settings()
