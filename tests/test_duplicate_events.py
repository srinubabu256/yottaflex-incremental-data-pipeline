"""
Automated tests for duplicate event handling: exact duplicates, conflicting duplicates, and repeated versions.
"""

from src.database.connection import DatabaseConnection
from src.processing.pipeline_runner import PipelineService
from src.config.constants import RejectionCode


def test_exact_duplicate_event_handling(temp_db: DatabaseConnection, create_event_csv):
    """
    Verifies that exact duplicate events are detected idempotently
    without double-counting revenue or duplicating records.
    """
    rows = [
        {
            "event_id": "EVT-DUP-1",
            "transaction_id": "TXN-DUP-1",
            "event_version": "1",
            "event_type": "CREATE",
            "event_timestamp": "2026-10-25T10:00:00Z",
            "business_date": "2026-10-25",
            "product_id": "PRD-0001",
            "customer_id": "CUST-0001",
            "amount_minor": "10000",
            "currency": "INR",
        }
    ]
    f1 = create_event_csv("batch1.csv", rows)
    service = PipelineService(temp_db)
    res1 = service.run_pipeline(f1)
    assert res1.inserted_count == 1
    assert res1.duplicate_count == 0

    # Second file with exact same event
    f2 = create_event_csv("batch2_renamed.csv", rows)
    res2 = service.run_pipeline(f2)
    # The file has a different name/path, but same content; file-checksum matches!
    # It will trigger file idempotency!
    assert res2.is_idempotent_skip is True

    # Now let's create a file with a NEW event AND the exact same old event
    rows_mixed = rows + [
        {
            "event_id": "EVT-NEW-2",
            "transaction_id": "TXN-NEW-2",
            "event_version": "1",
            "event_type": "CREATE",
            "event_timestamp": "2026-10-25T10:00:00Z",
            "business_date": "2026-10-25",
            "product_id": "PRD-0001",
            "customer_id": "CUST-0001",
            "amount_minor": "20000",
            "currency": "INR",
        }
    ]
    f3 = create_event_csv("batch3_mixed.csv", rows_mixed)
    res3 = service.run_pipeline(f3)
    assert res3.duplicate_count == 1
    assert res3.inserted_count == 1
    assert res3.accepted_count == 2

    # Verify database total revenue is 30000 (10000 + 20000), not 40000
    with temp_db.connection() as conn:
        rev = conn.execute("SELECT SUM(amount_minor) FROM transactions WHERE status = 'ACTIVE';").fetchone()[0]
        assert rev == 30000


def test_conflicting_duplicate_event_id(temp_db: DatabaseConnection, create_event_csv):
    """
    Verifies that duplicate event_id with different payload is quarantined.
    """
    rows1 = [
        {
            "event_id": "EVT-SAME-ID",
            "transaction_id": "TXN-A",
            "event_version": "1",
            "event_type": "CREATE",
            "event_timestamp": "2026-10-25T10:00:00Z",
            "business_date": "2026-10-25",
            "product_id": "PRD-0001",
            "customer_id": "CUST-0001",
            "amount_minor": "5000",
            "currency": "INR",
        }
    ]
    f1 = create_event_csv("file1.csv", rows1)
    service = PipelineService(temp_db)
    res1 = service.run_pipeline(f1)
    assert res1.inserted_count == 1

    # Conflicting event with same event_id but different transaction_id and amount
    rows2 = [
        {
            "event_id": "EVT-SAME-ID",
            "transaction_id": "TXN-B",
            "event_version": "1",
            "event_type": "CREATE",
            "event_timestamp": "2026-10-25T10:00:00Z",
            "business_date": "2026-10-25",
            "product_id": "PRD-0002",
            "customer_id": "CUST-0002",
            "amount_minor": "9999",
            "currency": "INR",
        }
    ]
    f2 = create_event_csv("file2_conflict.csv", rows2)
    res2 = service.run_pipeline(f2)
    assert res2.rejected_count == 1
    assert res2.status == "PARTIAL"

    # Verify quarantined in rejected_records
    with temp_db.connection() as conn:
        rej = conn.execute("SELECT * FROM rejected_records WHERE event_id = 'EVT-SAME-ID';").fetchone()
        assert rej is not None
        assert rej["rejection_code"] == RejectionCode.DUPLICATE_EVENT.value
