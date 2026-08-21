"""
Symmetric encryption for PHI using Fernet (AES-128-CBC + HMAC-SHA256).
Stands in for AWS KMS in this local prototype.
On first run, generates a key and stores it in .encryption_key
(production: inject via env or KMS).
"""
from __future__ import annotations
import os
import base64
import logging
from pathlib import Path
from app.config import settings

logger = logging.getLogger(__name__)

_KEY_FILE = Path(__file__).parent.parent / ".encryption_key"


def _load_or_generate_key() -> bytes:
    env_key = settings.encryption_key
    if env_key:
        return base64.urlsafe_b64decode(env_key.encode())

    if _KEY_FILE.exists():
        return _KEY_FILE.read_bytes()

    try:
        from cryptography.fernet import Fernet
        key = Fernet.generate_key()
        _KEY_FILE.write_bytes(key)
        logger.info("Generated new encryption key at %s", _KEY_FILE)
        return key
    except ImportError:
        logger.warning("cryptography not installed; encryption disabled")
        return b""


_key = _load_or_generate_key()


def encrypt(plaintext: str) -> str:
    if not _key:
        return plaintext  # passthrough if cryptography not available
    try:
        from cryptography.fernet import Fernet
        f = Fernet(_key)
        return f.encrypt(plaintext.encode()).decode()
    except Exception as exc:
        logger.error("Encryption failed: %s", exc)
        return plaintext


def decrypt(ciphertext: str) -> str:
    if not _key:
        return ciphertext
    try:
        from cryptography.fernet import Fernet
        f = Fernet(_key)
        return f.decrypt(ciphertext.encode()).decode()
    except Exception as exc:
        logger.error("Decryption failed: %s", exc)
        return ciphertext
