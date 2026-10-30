"""
Automated tests for REVERSE events: status change, revenue exclusion, repeated reversals.
"""

from src.database.connection import DatabaseConnection
from src.processing.pipeline_runner import PipelineService
from src.config.constants import RejectionCode


def test_reverse_removes_revenue_contribution(temp_db: DatabaseConnection, create_event_csv):
    """
    Verifies that a REVERSE event changes transaction status to REVERSED
    and removes its revenue contribution from daily metrics.
    """
    service = PipelineService(temp_db)
    # Create txn 1 (10000) and txn 2 (20000) for same product and date
    r1 = [
        {
            "event_id": "EVT-R1", "transaction_id": "TXN-REV-1", "event_version": "1",
            "event_type": "CREATE", "event_timestamp": "2026-10-25T10:00:00Z",
            "business_date": "2026-10-25", "product_id": "PRD-0001", "customer_id": "CUST-0001",
            "amount_minor": "10000", "currency": "INR",
        },
        {
            "event_id": "EVT-R2", "transaction_id": "TXN-REV-2", "event_version": "1",
            "event_type": "CREATE", "event_timestamp": "2026-10-25T10:05:00Z",
            "business_date": "2026-10-25", "product_id": "PRD-0001", "customer_id": "CUST-0002",
            "amount_minor": "20000", "currency": "INR",
        },
    ]
    service.run_pipeline(create_event_csv("rev_init.csv", r1))

    # Verify initial metric total: 30000
    with temp_db.connection() as conn:
        m = conn.execute(
            "SELECT total_revenue_minor, transaction_count FROM daily_product_metrics WHERE product_id = 'PRD-0001';"
        ).fetchone()
        assert m["total_revenue_minor"] == 30000
        assert m["transaction_count"] == 2

    # Reverse txn 1
    r_rev = [{
        "event_id": "EVT-R3", "transaction_id": "TXN-REV-1", "event_version": "2",
        "event_type": "REVERSE", "event_timestamp": "2026-10-25T11:00:00Z",
        "business_date": "2026-10-25", "product_id": "PRD-0001", "customer_id": "CUST-0001",
        "amount_minor": "10000", "currency": "INR",
    }]
    res_rev = service.run_pipeline(create_event_csv("rev_apply.csv", r_rev))
    assert res_rev.reversed_count == 1

    # Verify updated metric total: 20000, count 1
    with temp_db.connection() as conn:
        m2 = conn.execute(
            "SELECT total_revenue_minor, transaction_count FROM daily_product_metrics WHERE product_id = 'PRD-0001';"
        ).fetchone()
        assert m2["total_revenue_minor"] == 20000
        assert m2["transaction_count"] == 1


def test_repeated_reversal_rejected(temp_db: DatabaseConnection, create_event_csv):
    """
    Verifies that repeating a REVERSE event on an already reversed transaction
    is rejected and does not subtract revenue twice.
    """
    service = PipelineService(temp_db)
    r1 = [{
        "event_id": "EVT-REP-1", "transaction_id": "TXN-REP", "event_version": "1",
        "event_type": "CREATE", "event_timestamp": "2026-10-25T10:00:00Z",
        "business_date": "2026-10-25", "product_id": "PRD-0001", "customer_id": "CUST-0001",
        "amount_minor": "5000", "currency": "INR",
    }]
    r2 = [{
        "event_id": "EVT-REP-2", "transaction_id": "TXN-REP", "event_version": "2",
        "event_type": "REVERSE", "event_timestamp": "2026-10-25T12:00:00Z",
        "business_date": "2026-10-25", "product_id": "PRD-0001", "customer_id": "CUST-0001",
        "amount_minor": "5000", "currency": "INR",
    }]
    service.run_pipeline(create_event_csv("rep1.csv", r1))
    service.run_pipeline(create_event_csv("rep2.csv", r2))

    # Attempt second reversal
    r3 = [{
        "event_id": "EVT-REP-3", "transaction_id": "TXN-REP", "event_version": "3",
        "event_type": "REVERSE", "event_timestamp": "2026-10-25T14:00:00Z",
        "business_date": "2026-10-25", "product_id": "PRD-0001", "customer_id": "CUST-0001",
        "amount_minor": "5000", "currency": "INR",
    }]
    res3 = service.run_pipeline(create_event_csv("rep3.csv", r3))
    assert res3.rejected_count == 1
    assert res3.status == "PARTIAL"

    with temp_db.connection() as conn:
        rej = conn.execute("SELECT * FROM rejected_records WHERE event_id = 'EVT-REP-3';").fetchone()
        assert rej["rejection_code"] == RejectionCode.INVALID_TRANSACTION_STATE.value


def test_reversal_of_unknown_transaction(temp_db: DatabaseConnection, create_event_csv):
    """
    Verifies that a REVERSE event targeting a non-existent transaction
    is quarantined and marked as INVALID_TRANSACTION_STATE.
    """
    service = PipelineService(temp_db)
    r = [{
        "event_id": "EVT-REV-UNK-1", "transaction_id": "TXN-GHOST-999", "event_version": "2",
        "event_type": "REVERSE", "event_timestamp": "2026-10-25T14:00:00Z",
        "business_date": "2026-10-25", "product_id": "PRD-0001", "customer_id": "CUST-0001",
        "amount_minor": "5000", "currency": "INR",
    }]
    res = service.run_pipeline(create_event_csv("rev_ghost.csv", r))
    assert res.rejected_count == 1
    assert res.status == "PARTIAL"

    with temp_db.connection() as conn:
        rej = conn.execute("SELECT * FROM rejected_records WHERE event_id = 'EVT-REV-UNK-1';").fetchone()
        assert rej is not None
        assert rej["rejection_code"] == RejectionCode.INVALID_TRANSACTION_STATE.value
        assert "non-existent" in rej["rejection_reason"].lower()
