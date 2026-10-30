"""
Automated tests for CSV ingestion, fingerprinting, and batch streaming.
"""

from pathlib import Path
import pytest
from src.ingestion.csv_reader import StreamingCSVReader, IngestionError
from src.ingestion.fingerprint import compute_file_checksum, compute_payload_hash
from src.validation.schema_validator import validate_csv_schema, SchemaValidationError
from src.config.constants import CANONICAL_COLUMNS


def test_valid_csv_batch_streaming(temp_dir: Path, create_event_csv):
    """Verifies that StreamingCSVReader streams rows in expected batches."""
    rows = [
        {
            "event_id": f"EVT-{i}",
            "transaction_id": f"TXN-{i}",
            "event_version": "1",
            "event_type": "CREATE",
            "event_timestamp": "2026-10-25T10:00:00Z",
            "business_date": "2026-10-25",
            "product_id": "PRD-0001",
            "customer_id": "CUST-0001",
            "amount_minor": "1000",
            "currency": "INR",
        }
        for i in range(1, 25)
    ]
    csv_file = create_event_csv("batch_stream.csv", rows)

    reader = StreamingCSVReader(csv_file, batch_size=10)
    batches = list(reader.read_batches())
    assert len(batches) == 3  # 10 + 10 + 4
    headers, batch1 = batches[0]
    assert headers == CANONICAL_COLUMNS
    assert len(batch1) == 10
    assert batch1[0][0] == 2  # First row number is 2
    assert batch1[0][1]["event_id"] == "EVT-1"


def test_empty_csv_file(temp_dir: Path):
    """Verifies that an empty (0 byte) file raises IngestionError."""
    empty_file = temp_dir / "empty.csv"
    empty_file.write_text("", encoding="utf-8")

    reader = StreamingCSVReader(empty_file)
    with pytest.raises(IngestionError, match="empty"):
        list(reader.read_batches())


def test_missing_file():
    """Verifies that a non-existent file raises FileNotFoundError."""
    reader = StreamingCSVReader("non_existent_file.csv")
    with pytest.raises(FileNotFoundError):
        list(reader.read_batches())


def test_schema_validator_missing_column():
    """Verifies that missing columns trigger SchemaValidationError."""
    incomplete_headers = ["event_id", "transaction_id", "event_type"]
    with pytest.raises(SchemaValidationError, match="Missing required columns"):
        validate_csv_schema(incomplete_headers)


def test_schema_validator_unexpected_column():
    """Verifies that unexpected columns trigger SchemaValidationError."""
    extra_headers = CANONICAL_COLUMNS + ["unknown_column"]
    with pytest.raises(SchemaValidationError, match="Unexpected columns"):
        validate_csv_schema(extra_headers)


def test_file_fingerprint_consistency(temp_dir: Path):
    """Verifies that identical file contents produce identical SHA-256 fingerprints."""
    f1 = temp_dir / "f1.csv"
    f2 = temp_dir / "f2.csv"
    f1.write_text("header\nval1,val2", encoding="utf-8")
    f2.write_text("header\nval1,val2", encoding="utf-8")

    assert compute_file_checksum(f1) == compute_file_checksum(f2)


def test_latin1_encoding_fallback(temp_dir: Path):
    """Verifies that files with Latin-1 specific characters are read without crash."""
    f_latin = temp_dir / "latin1.csv"
    content = "event_id,transaction_id,event_version,event_type,event_timestamp,business_date,product_id,customer_id,amount_minor,currency\n"
    content += "EVT-1,TXN-1,1,CREATE,2026-10-25T10:00:00Z,2026-10-25,PRD-0001,CUST-0001,1000,INR\n"
    f_latin.write_bytes(content.encode("latin-1"))

    reader = StreamingCSVReader(f_latin)
    batches = list(reader.read_batches())
    assert len(batches) == 1
    assert len(batches[0][1]) == 1
