"""
File and payload hashing / fingerprinting utilities.
Ensures file-level and event-level idempotency through SHA-256 digests.
"""

import hashlib
from pathlib import Path
from src.config.constants import CANONICAL_COLUMNS


def compute_file_checksum(file_path: Path, chunk_size: int = 65536) -> str:
    """
    Computes a SHA-256 checksum of the specified file by reading in chunks.
    Works efficiently on files of any size.
    """
    if not file_path.exists():
        raise FileNotFoundError(f"File not found for checksum: {file_path}")

    hasher = hashlib.sha256()
    with open(file_path, "rb") as f:
        while chunk := f.read(chunk_size):
            hasher.update(chunk)
    return hasher.hexdigest()


def compute_payload_hash(record: dict[str, str | int]) -> str:
    """
    Computes a deterministic SHA-256 hash of canonical event fields.
    Normalizes whitespace and formats to guarantee consistent deduplication.
    """
    tokens = []
    for col in CANONICAL_COLUMNS:
        val = record.get(col, "")
        tokens.append(f"{col}:{str(val).strip()}")
    normalized_repr = "|".join(tokens)
    return hashlib.sha256(normalized_repr.encode("utf-8")).hexdigest()
