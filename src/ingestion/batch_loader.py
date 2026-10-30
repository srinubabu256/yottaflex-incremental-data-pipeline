"""
Batch loader combining CSV streaming and file fingerprinting.
"""

from pathlib import Path
from src.ingestion.csv_reader import StreamingCSVReader, IngestionError
from src.ingestion.fingerprint import compute_file_checksum
from src.config.logging_config import get_logger

logger = get_logger(__name__)


class BatchLoader:
    """Coordinates file fingerprinting and batch streaming for ingestion."""

    def __init__(self, file_path: Path | str, batch_size: int = 5000):
        self.file_path = Path(file_path)
        self.batch_size = batch_size
        self._checksum: str | None = None

    @property
    def checksum(self) -> str:
        """Computes or returns cached SHA-256 checksum."""
        if self._checksum is None:
            self._checksum = compute_file_checksum(self.file_path)
        return self._checksum

    def load_batches(self):
        """Yields (headers, batch_rows) tuples."""
        reader = StreamingCSVReader(self.file_path, batch_size=self.batch_size)
        yield from reader.read_batches()
