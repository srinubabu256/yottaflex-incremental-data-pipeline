"""
Automated tests for independent reconciliation: PASS, FAIL, mismatch detection, and edge cases.
"""

from src.database.connection import DatabaseConnection
from src.processing.pipeline_runner import PipelineService
from src.reconciliation.checks import perform_full_reconciliation
from src.reconciliation.report import generate_reconciliation_report


def test_reconciliation_passes_on_valid_data(temp_db: DatabaseConnection, create_event_csv):
    """Verifies that an untouched database with processed transactions produces 100% PASS."""
    service = PipelineService(temp_db)
    rows = [
        {
            "event_id": f"EVT-REC-{i}", "transaction_id": f"TXN-REC-{i}", "event_version": "1",
            "event_type": "CREATE", "event_timestamp": "2026-10-25T10:00:00Z",
            "business_date": "2026-10-25", "product_id": "PRD-0001", "customer_id": "CUST-0001",
            "amount_minor": "10000", "currency": "INR",
        }
        for i in range(1, 5)
    ]
    service.run_pipeline(create_event_csv("recon_pass.csv", rows))

    checks, passed, failed = generate_reconciliation_report(temp_db)
    assert failed == 0
    assert passed > 0


def test_reconciliation_detects_deliberate_tampering(temp_db: DatabaseConnection, create_event_csv):
    """
    Verifies that deliberate tampering with an aggregate table (e.g. artificial inflation)
    is caught and flagged as FAIL by reconciliation.
    """
    service = PipelineService(temp_db)
    rows = [
        {
            "event_id": "EVT-TAMP-1", "transaction_id": "TXN-TAMP-1", "event_version": "1",
            "event_type": "CREATE", "event_timestamp": "2026-10-25T10:00:00Z",
            "business_date": "2026-10-25", "product_id": "PRD-0001", "customer_id": "CUST-0001",
            "amount_minor": "10000", "currency": "INR",
        }
    ]
    service.run_pipeline(create_event_csv("tamper_init.csv", rows))

    # Deliberately tamper with the aggregate table
    with temp_db.transaction() as conn:
        conn.execute(
            """
            UPDATE daily_product_metrics
            SET total_revenue_minor = 999999
            WHERE business_date = '2026-10-25' AND product_id = 'PRD-0001';
            """
        )

    checks, passed, failed = generate_reconciliation_report(temp_db)
    assert failed > 0

    failed_checks = [c for c in checks if c.status == "FAIL"]
    tampered_metric = [c for c in failed_checks if c.metric_name == "total_revenue_minor"]
    assert len(tampered_metric) == 1
    assert tampered_metric[0].expected_value == "10000"
    assert tampered_metric[0].actual_value == "999999"


def test_domain_edge_case_reversal_with_concurrent_late_arrival(temp_db: DatabaseConnection, create_event_csv):
    """
    Documented Domain-Specific Edge Case 2: Reversal with Concurrent Historical Late Arrival.
    A transaction is created at v1, reversed at v2.
    Then, an older/duplicate v1 event arrives late out of order.
    The late event must be quarantined and MUST NOT resurrect the reversed transaction
    nor inject stale revenue into daily metrics.
    """
    service = PipelineService(temp_db)

    # 1. Create transaction (v1)
    r1 = [{
        "event_id": "EVT-REV-LATE-1", "transaction_id": "TXN-LATE-EDGE", "event_version": "1",
        "event_type": "CREATE", "event_timestamp": "2026-10-25T10:00:00Z",
        "business_date": "2026-10-25", "product_id": "PRD-0001", "customer_id": "CUST-0001",
        "amount_minor": "50000", "currency": "INR",
    }]
    service.run_pipeline(create_event_csv("edge_v1.csv", r1))

    # 2. Reverse transaction (v2)
    r2 = [{
        "event_id": "EVT-REV-LATE-2", "transaction_id": "TXN-LATE-EDGE", "event_version": "2",
        "event_type": "REVERSE", "event_timestamp": "2026-10-25T11:00:00Z",
        "business_date": "2026-10-25", "product_id": "PRD-0001", "customer_id": "CUST-0001",
        "amount_minor": "50000", "currency": "INR",
    }]
    service.run_pipeline(create_event_csv("edge_v2.csv", r2))

    # 3. Concurrent out-of-order late arrival claiming to be v1 with different event_id
    r3 = [{
        "event_id": "EVT-REV-LATE-STALE", "transaction_id": "TXN-LATE-EDGE", "event_version": "1",
        "event_type": "CREATE", "event_timestamp": "2026-10-25T09:30:00Z",
        "business_date": "2026-10-25", "product_id": "PRD-0001", "customer_id": "CUST-0001",
        "amount_minor": "50000", "currency": "INR",
    }]
    res3 = service.run_pipeline(create_event_csv("edge_v1_stale.csv", r3))
    assert res3.rejected_count == 1
    assert res3.status == "PARTIAL"

    # Verify transaction remains REVERSED and active revenue remains 0
    with temp_db.connection() as conn:
        txn = conn.execute("SELECT status FROM transactions WHERE transaction_id = 'TXN-LATE-EDGE';").fetchone()
        assert txn["status"] == "REVERSED"

        # Check reconciliation: 0 failures, total active revenue is 0
        checks, passed, failed = generate_reconciliation_report(temp_db)
        assert failed == 0
