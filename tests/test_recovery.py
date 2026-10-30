"""
Automated tests for error recovery, rollback, and partial failure quarantine.
"""

from unittest.mock import patch
from src.database.connection import DatabaseConnection
from src.processing.pipeline_runner import PipelineService
from src.config.constants import PipelineRunStatus


def test_row_level_quarantine_allows_valid_records(temp_db: DatabaseConnection, create_event_csv):
    """
    Verifies that a batch containing valid and invalid rows continues processing
    valid rows, quarantines invalid rows, and marks the run status as PARTIAL.
    """
    rows = [
        # Valid row 1
        {
            "event_id": "EVT-REC-1", "transaction_id": "TXN-REC-1", "event_version": "1",
            "event_type": "CREATE", "event_timestamp": "2026-10-25T10:00:00Z",
            "business_date": "2026-10-25", "product_id": "PRD-0001", "customer_id": "CUST-0001",
            "amount_minor": "10000", "currency": "INR",
        },
        # Invalid row (unknown customer)
        {
            "event_id": "EVT-REC-INV", "transaction_id": "TXN-REC-2", "event_version": "1",
            "event_type": "CREATE", "event_timestamp": "2026-10-25T10:00:00Z",
            "business_date": "2026-10-25", "product_id": "PRD-0001", "customer_id": "CUST-NONEXISTENT",
            "amount_minor": "20000", "currency": "INR",
        },
        # Valid row 2
        {
            "event_id": "EVT-REC-3", "transaction_id": "TXN-REC-3", "event_version": "1",
            "event_type": "CREATE", "event_timestamp": "2026-10-25T10:00:00Z",
            "business_date": "2026-10-25", "product_id": "PRD-0001", "customer_id": "CUST-0001",
            "amount_minor": "30000", "currency": "INR",
        },
    ]
    f = create_event_csv("mixed_batch.csv", rows)
    service = PipelineService(temp_db)
    res = service.run_pipeline(f)

    assert res.status == PipelineRunStatus.PARTIAL.value
    assert res.input_count == 3
    assert res.accepted_count == 2
    assert res.rejected_count == 1
    assert res.inserted_count == 2

    with temp_db.connection() as conn:
        # Valid transactions exist
        txns = conn.execute("SELECT transaction_id FROM transactions WHERE transaction_id IN ('TXN-REC-1', 'TXN-REC-3');").fetchall()
        assert len(txns) == 2

        # Quarantined record exists in rejected_records
        rej = conn.execute("SELECT * FROM rejected_records WHERE event_id = 'EVT-REC-INV';").fetchone()
        assert rej is not None


def test_fatal_failure_marks_run_failed(temp_db: DatabaseConnection, create_event_csv):
    """
    Verifies that a fatal unhandled database or processing failure
    properly logs the failure reason and marks pipeline run as FAILED.
    """
    rows = [
        {
            "event_id": "EVT-FATAL-1", "transaction_id": "TXN-FATAL-1", "event_version": "1",
            "event_type": "CREATE", "event_timestamp": "2026-10-25T10:00:00Z",
            "business_date": "2026-10-25", "product_id": "PRD-0001", "customer_id": "CUST-0001",
            "amount_minor": "10000", "currency": "INR",
        }
    ]
    f = create_event_csv("fatal.csv", rows)
    service = PipelineService(temp_db)

    with patch("src.processing.event_processor.EventProcessor.process_batch", side_effect=RuntimeError("Simulated Disk Crash")):
        res = service.run_pipeline(f)
        assert res.status == PipelineRunStatus.FAILED.value
        assert "Simulated Disk Crash" in res.failure_reason
