"""
Streaming CSV Reader for high-throughput, memory-efficient ingestion.
"""

import csv
from pathlib import Path
from typing import Generator, Any
from src.config.logging_config import get_logger

logger = get_logger(__name__)


class IngestionError(Exception):
    """Raised when CSV structure or file reading fails catastrophically."""
    pass


class StreamingCSVReader:
    """Streams CSV rows in configurable batch sizes with exact row tracking."""

    def __init__(self, file_path: Path | str, batch_size: int = 5000):
        self.file_path = Path(file_path)
        self.batch_size = batch_size

    def read_batches(
        self,
    ) -> Generator[tuple[list[str], list[tuple[int, dict[str, str]]]], None, None]:
        """
        Yields (headers, batch_of_tuples) where each item in batch is (source_row_number, row_dict).
        If the file has only headers or is empty, handles gracefully.
        """
        if not self.file_path.exists():
            raise FileNotFoundError(f"Input file does not exist: {self.file_path}")

        # Check if file is completely 0-byte
        if self.file_path.stat().st_size == 0:
            raise IngestionError("File is empty (0 bytes).")

        # Attempt UTF-8 first, fallback to Latin-1 if decode error
        encodings = ["utf-8", "utf-8-sig", "latin-1"]
        file_obj = None
        for enc in encodings:
            try:
                f = open(self.file_path, "r", encoding=enc, newline="")
                # Probe first line
                pos = f.tell()
                f.readline()
                f.seek(pos)
                file_obj = f
                break
            except (UnicodeDecodeError, Exception):
                if file_obj:
                    file_obj.close()
                continue

        if file_obj is None:
            raise IngestionError(f"Could not open file with supported encodings: {self.file_path}")

        try:
            reader = csv.reader(file_obj)
            try:
                header_row = next(reader, None)
            except Exception as e:
                raise IngestionError(f"Malformed CSV header: {e}") from e

            if header_row is None:
                raise IngestionError("File contains no data or header.")

            headers = [h.strip() for h in header_row]

            batch: list[tuple[int, dict[str, str]]] = []
            row_idx = 1  # Header was row 1

            for raw_row in reader:
                row_idx += 1
                # Check column count
                if len(raw_row) != len(headers):
                    # Pad or construct dict with what we have
                    row_dict = {
                        headers[i]: (raw_row[i].strip() if i < len(raw_row) else "")
                        for i in range(len(headers))
                    }
                else:
                    row_dict = {headers[i]: raw_row[i].strip() for i in range(len(headers))}

                batch.append((row_idx, row_dict))

                if len(batch) >= self.batch_size:
                    yield headers, batch
                    batch = []

            if batch:
                yield headers, batch

            # If no data rows were yielded at all (file had only header)
            if row_idx == 1:
                yield headers, []

        finally:
            file_obj.close()
