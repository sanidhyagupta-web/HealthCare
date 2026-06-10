import hashlib
import re


def _normalise(text: str) -> str:
    """Strip extra whitespace before hashing so minor formatting diffs don't create duplicates."""
    return re.sub(r"\s+", " ", text).strip().lower()


def compute_hash(text: str) -> str:
    normalised = _normalise(text)
    return hashlib.sha256(normalised.encode("utf-8")).hexdigest()
