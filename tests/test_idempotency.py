"""
Automated tests for file-level and event-level idempotency.
"""

from src.database.connection import DatabaseConnection
from src.processing.pipeline_runner import PipelineService


def test_file_level_idempotency_rerun(temp_db: DatabaseConnection, create_event_csv):
    """Verifies that re-running the exact same file is safely skipped."""
    service = PipelineService(temp_db)
    rows = [
        {
            "event_id": "EVT-IDEM-1", "transaction_id": "TXN-IDEM-1", "event_version": "1",
            "event_type": "CREATE", "event_timestamp": "2026-10-25T10:00:00Z",
            "business_date": "2026-10-25", "product_id": "PRD-0001", "customer_id": "CUST-0001",
            "amount_minor": "12000", "currency": "INR",
        }
    ]
    f = create_event_csv("idem1.csv", rows)
    res1 = service.run_pipeline(f)
    assert res1.inserted_count == 1
    assert res1.is_idempotent_skip is False

    # Second run of exact same file
    res2 = service.run_pipeline(f)
    assert res2.is_idempotent_skip is True
    assert res2.inserted_count == 0


def test_renamed_file_with_same_events_idempotent(temp_db: DatabaseConnection, create_event_csv):
    """
    Verifies that a renamed file containing identical bytes/events is detected
    by SHA-256 checksum and does not cause duplicate transactions.
    """
    service = PipelineService(temp_db)
    rows = [
        {
            "event_id": "EVT-IDEM-2", "transaction_id": "TXN-IDEM-2", "event_version": "1",
            "event_type": "CREATE", "event_timestamp": "2026-10-25T10:00:00Z",
            "business_date": "2026-10-25", "product_id": "PRD-0001", "customer_id": "CUST-0001",
            "amount_minor": "15000", "currency": "INR",
        }
    ]
    f_orig = create_event_csv("orig_events.csv", rows)
    service.run_pipeline(f_orig)

    # Renamed file with identical content
    f_renamed = create_event_csv("renamed_copy.csv", rows)
    res = service.run_pipeline(f_renamed)
    assert res.is_idempotent_skip is True

    with temp_db.connection() as conn:
        count = conn.execute("SELECT COUNT(*) FROM transactions WHERE transaction_id = 'TXN-IDEM-2';").fetchone()[0]
        assert count == 1
