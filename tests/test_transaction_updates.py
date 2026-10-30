"""
Automated tests for UPDATE events: attribute changes, date shifts, and reversal blocking.
"""

from src.database.connection import DatabaseConnection
from src.processing.pipeline_runner import PipelineService
from src.config.constants import RejectionCode


def test_update_amount_and_date(temp_db: DatabaseConnection, create_event_csv):
    """
    Verifies that an UPDATE successfully modifies amount and shifts business_date,
    updating the authoritative transaction state.
    """
    service = PipelineService(temp_db)
    r1 = [{
        "event_id": "EVT-U1", "transaction_id": "TXN-UPD-TEST", "event_version": "1",
        "event_type": "CREATE", "event_timestamp": "2026-10-25T10:00:00Z",
        "business_date": "2026-10-25", "product_id": "PRD-0001", "customer_id": "CUST-0001",
        "amount_minor": "10000", "currency": "INR",
    }]
    service.run_pipeline(create_event_csv("u1.csv", r1))

    # Update amount to 15000 and business_date to 2026-10-26
    r2 = [{
        "event_id": "EVT-U2", "transaction_id": "TXN-UPD-TEST", "event_version": "2",
        "event_type": "UPDATE", "event_timestamp": "2026-10-26T11:00:00Z",
        "business_date": "2026-10-26", "product_id": "PRD-0001", "customer_id": "CUST-0001",
        "amount_minor": "15000", "currency": "INR",
    }]
    res2 = service.run_pipeline(create_event_csv("u2.csv", r2))
    assert res2.updated_count == 1

    with temp_db.connection() as conn:
        txn = conn.execute("SELECT * FROM transactions WHERE transaction_id = 'TXN-UPD-TEST';").fetchone()
        assert txn["amount_minor"] == 15000
        assert txn["business_date"] == "2026-10-26"
        assert txn["latest_version"] == 2


def test_update_after_reversal_rejected(temp_db: DatabaseConnection, create_event_csv):
    """
    Verifies that an UPDATE targeting an already REVERSED transaction is rejected.
    """
    service = PipelineService(temp_db)
    # Create
    r1 = [{
        "event_id": "EVT-REV-CREATE", "transaction_id": "TXN-TERM", "event_version": "1",
        "event_type": "CREATE", "event_timestamp": "2026-10-25T10:00:00Z",
        "business_date": "2026-10-25", "product_id": "PRD-0001", "customer_id": "CUST-0001",
        "amount_minor": "5000", "currency": "INR",
    }]
    # Reverse
    r2 = [{
        "event_id": "EVT-REV-REVERSE", "transaction_id": "TXN-TERM", "event_version": "2",
        "event_type": "REVERSE", "event_timestamp": "2026-10-25T12:00:00Z",
        "business_date": "2026-10-25", "product_id": "PRD-0001", "customer_id": "CUST-0001",
        "amount_minor": "5000", "currency": "INR",
    }]
    service.run_pipeline(create_event_csv("term1.csv", r1))
    service.run_pipeline(create_event_csv("term2.csv", r2))

    # Attempt UPDATE
    r3 = [{
        "event_id": "EVT-REV-UPDATE", "transaction_id": "TXN-TERM", "event_version": "3",
        "event_type": "UPDATE", "event_timestamp": "2026-10-25T14:00:00Z",
        "business_date": "2026-10-25", "product_id": "PRD-0001", "customer_id": "CUST-0001",
        "amount_minor": "6000", "currency": "INR",
    }]
    res3 = service.run_pipeline(create_event_csv("term3.csv", r3))
    assert res3.rejected_count == 1
    assert res3.status == "PARTIAL"

    with temp_db.connection() as conn:
        rej = conn.execute("SELECT * FROM rejected_records WHERE event_id = 'EVT-REV-UPDATE';").fetchone()
        assert rej["rejection_code"] == RejectionCode.INVALID_TRANSACTION_STATE.value
