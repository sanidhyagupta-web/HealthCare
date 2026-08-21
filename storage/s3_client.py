"""
S3 storage client with KMS server-side encryption.

All uploads use SSE-KMS. Downloads are transparently decrypted by AWS.
This is the single choke-point for all raw/intermediate file I/O in the
ingestion pipeline — no plaintext PII ever lands on local disk.

S3 key layout:
  raw/{doc_id}/{original_filename}        ← uploaded doc before parsing
  processed/{doc_id}/raw.txt              ← extracted plaintext (pre-markdown)
  processed/{doc_id}/markdown.md          ← structured markdown (pre-chunking)
"""
from __future__ import annotations
import logging
import os
import tempfile
from pathlib import Path

import boto3
from botocore.exceptions import ClientError

from app.config import settings

logger = logging.getLogger(__name__)

_s3 = None


def _client():
    global _s3
    if _s3 is None:
        kwargs = {"region_name": settings.aws_region}
        if settings.aws_access_key_id:
            kwargs["aws_access_key_id"] = settings.aws_access_key_id
            kwargs["aws_secret_access_key"] = settings.aws_secret_access_key
        if settings.aws_session_token:
            kwargs["aws_session_token"] = settings.aws_session_token
        _s3 = boto3.client("s3", **kwargs)
    return _s3


def _kms_args() -> dict:
    if settings.kms_key_id:
        return {"ServerSideEncryption": "aws:kms", "SSEKMSKeyId": settings.kms_key_id}
    # Fall back to S3-managed keys (SSE-S3) when no CMK is configured
    return {"ServerSideEncryption": "AES256"}


def upload(s3_key: str, content: bytes | str) -> None:
    """Upload bytes or str to S3 with server-side encryption."""
    if isinstance(content, str):
        content = content.encode("utf-8")
    _client().put_object(
        Bucket=settings.s3_bucket,
        Key=s3_key,
        Body=content,
        **_kms_args(),
    )
    logger.debug("S3 upload: s3://%s/%s (%d bytes)", settings.s3_bucket, s3_key, len(content))


def upload_file(s3_key: str, local_path: str | Path) -> None:
    """Upload a local file to S3 with server-side encryption."""
    _client().upload_file(
        Filename=str(local_path),
        Bucket=settings.s3_bucket,
        Key=s3_key,
        ExtraArgs=_kms_args(),
    )
    logger.debug("S3 upload_file: %s → s3://%s/%s", local_path, settings.s3_bucket, s3_key)


def download_bytes(s3_key: str) -> bytes:
    """Download an S3 object and return its bytes (KMS-decrypted transparently)."""
    resp = _client().get_object(Bucket=settings.s3_bucket, Key=s3_key)
    data = resp["Body"].read()
    logger.debug("S3 download: s3://%s/%s (%d bytes)", settings.s3_bucket, s3_key, len(data))
    return data


def download_to_tempfile(s3_key: str, suffix: str = "") -> str:
    """
    Download an S3 object to a named temp file.
    Caller is responsible for deleting it (os.unlink) after use.
    Returns the local temp file path.
    """
    data = download_bytes(s3_key)
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
    tmp.write(data)
    tmp.flush()
    tmp.close()
    logger.debug("S3 downloaded to tempfile: %s", tmp.name)
    return tmp.name


def delete(s3_key: str) -> None:
    """Delete an object from S3 (best-effort, logs on failure)."""
    try:
        _client().delete_object(Bucket=settings.s3_bucket, Key=s3_key)
        logger.debug("S3 delete: s3://%s/%s", settings.s3_bucket, s3_key)
    except ClientError as e:
        logger.warning("S3 delete failed for %s: %s", s3_key, e)
