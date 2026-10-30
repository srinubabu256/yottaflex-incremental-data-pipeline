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


def test_retry_after_fatal_failure_recovers_cleanly(temp_db: DatabaseConnection, create_event_csv):
    """
    Verifies Phase 9 requirement:
    When a run fails due to infrastructure error, it does not commit partial corruption,
    and retrying the exact file afterwards executes successfully without duplicate ledger rows.
    """
    rows = [
        {
            "event_id": "EVT-RETRY-1", "transaction_id": "TXN-RETRY-1", "event_version": "1",
            "event_type": "CREATE", "event_timestamp": "2026-10-25T10:00:00Z",
            "business_date": "2026-10-25", "product_id": "PRD-0001", "customer_id": "CUST-0001",
            "amount_minor": "75000", "currency": "INR",
        }
    ]
    f = create_event_csv("retry_test.csv", rows)
    service = PipelineService(temp_db)

    # First attempt fails fatally
    with patch("src.processing.event_processor.EventProcessor.process_batch", side_effect=RuntimeError("Transient DB Outage")):
        res_fail = service.run_pipeline(f)
        assert res_fail.status == PipelineRunStatus.FAILED.value

    # Second attempt succeeds without mocking failure
    res_success = service.run_pipeline(f)
    assert res_success.status == PipelineRunStatus.SUCCESS.value
    assert res_success.inserted_count == 1
    assert res_success.accepted_count == 1

    with temp_db.connection() as conn:
        # Exactly one source_event and one transaction exist
        evts = conn.execute("SELECT COUNT(*) FROM source_events WHERE transaction_id = 'TXN-RETRY-1';").fetchone()[0]
        assert evts == 1
        txns = conn.execute("SELECT COUNT(*) FROM transactions WHERE transaction_id = 'TXN-RETRY-1';").fetchone()[0]
        assert txns == 1


def test_process_failed_file_after_correcting_issue(temp_db: DatabaseConnection, create_event_csv):
    """
    Verifies that when a completely invalid file is processed,
    it records rejections, and after correcting the file and reprocessing,
    the valid data is accepted and accurately aggregated.
    """
    service = PipelineService(temp_db)

    # Initial file: negative amount (completely invalid)
    bad_rows = [
        {
            "event_id": "EVT-FIX-1", "transaction_id": "TXN-FIX-1", "event_version": "1",
            "event_type": "CREATE", "event_timestamp": "2026-10-25T10:00:00Z",
            "business_date": "2026-10-25", "product_id": "PRD-0001", "customer_id": "CUST-0001",
            "amount_minor": "-5000", "currency": "INR",
        }
    ]
    f_bad = create_event_csv("bad_file.csv", bad_rows)
    res_bad = service.run_pipeline(f_bad)
    assert res_bad.rejected_count == 1
    assert res_bad.accepted_count == 0

    # Corrected file: positive amount
    good_rows = [
        {
            "event_id": "EVT-FIX-1", "transaction_id": "TXN-FIX-1", "event_version": "1",
            "event_type": "CREATE", "event_timestamp": "2026-10-25T10:00:00Z",
            "business_date": "2026-10-25", "product_id": "PRD-0001", "customer_id": "CUST-0001",
            "amount_minor": "5000", "currency": "INR",
        }
    ]
    f_good = create_event_csv("good_file.csv", good_rows)
    res_good = service.run_pipeline(f_good)
    assert res_good.accepted_count == 1
    assert res_good.rejected_count == 0

    with temp_db.connection() as conn:
        txn = conn.execute("SELECT * FROM transactions WHERE transaction_id = 'TXN-FIX-1';").fetchone()
        assert txn is not None
        assert txn["amount_minor"] == 5000
