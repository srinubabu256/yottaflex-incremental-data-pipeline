"""
Automated tests for event versioning logic and snapshot handling.
"""

from src.database.connection import DatabaseConnection
from src.processing.pipeline_runner import PipelineService
from src.processing.version_manager import evaluate_event_version, VersionAction
from src.config.constants import RejectionCode


def test_evaluate_event_version_matrix():
    """Unit test for evaluate_event_version state transitions."""
    # Duplicate checks
    assert evaluate_event_version(1, 1, is_duplicate=True, is_exact_match=True) == VersionAction.EXACT_DUPLICATE
    assert evaluate_event_version(1, 1, is_duplicate=True, is_exact_match=False) == VersionAction.CONFLICT

    # New transaction
    assert evaluate_event_version(None, 1, is_duplicate=False, is_exact_match=False) == VersionAction.APPLY
    assert evaluate_event_version(None, 2, is_duplicate=False, is_exact_match=False) == VersionAction.APPLY

    # Subsequent versions
    assert evaluate_event_version(1, 2, is_duplicate=False, is_exact_match=False) == VersionAction.APPLY
    assert evaluate_event_version(2, 2, is_duplicate=False, is_exact_match=False) == VersionAction.CONFLICT
    assert evaluate_event_version(3, 2, is_duplicate=False, is_exact_match=False) == VersionAction.LATE_IGNORED


def test_create_requires_version_one(temp_db: DatabaseConnection, create_event_csv):
    """Verifies that a CREATE event with version > 1 is rejected."""
    rows = [
        {
            "event_id": "EVT-V2",
            "transaction_id": "TXN-V2",
            "event_version": "2",  # Should be 1
            "event_type": "CREATE",
            "event_timestamp": "2026-10-25T10:00:00Z",
            "business_date": "2026-10-25",
            "product_id": "PRD-0001",
            "customer_id": "CUST-0001",
            "amount_minor": "5000",
            "currency": "INR",
        }
    ]
    f = create_event_csv("bad_create_ver.csv", rows)
    service = PipelineService(temp_db)
    res = service.run_pipeline(f)
    assert res.rejected_count == 1
    assert res.status == "PARTIAL"

    with temp_db.connection() as conn:
        rej = conn.execute("SELECT * FROM rejected_records WHERE event_id = 'EVT-V2';").fetchone()
        assert rej["rejection_code"] == RejectionCode.VERSION_CONFLICT.value


def test_higher_version_without_intermediate(temp_db: DatabaseConnection, create_event_csv):
    """
    Verifies that a higher version arriving before an intermediate version
    (e.g., version 3 after version 1) is accepted as a complete replacement snapshot.
    """
    rows1 = [
        {
            "event_id": "EVT-V1",
            "transaction_id": "TXN-SNAP",
            "event_version": "1",
            "event_type": "CREATE",
            "event_timestamp": "2026-10-25T10:00:00Z",
            "business_date": "2026-10-25",
            "product_id": "PRD-0001",
            "customer_id": "CUST-0001",
            "amount_minor": "1000",
            "currency": "INR",
        }
    ]
    f1 = create_event_csv("snap_v1.csv", rows1)
    service = PipelineService(temp_db)
    service.run_pipeline(f1)

    # Jump straight to version 3
    rows2 = [
        {
            "event_id": "EVT-V3",
            "transaction_id": "TXN-SNAP",
            "event_version": "3",
            "event_type": "UPDATE",
            "event_timestamp": "2026-10-25T14:00:00Z",
            "business_date": "2026-10-25",
            "product_id": "PRD-0001",
            "customer_id": "CUST-0001",
            "amount_minor": "3500",
            "currency": "INR",
        }
    ]
    f2 = create_event_csv("snap_v3.csv", rows2)
    res2 = service.run_pipeline(f2)
    assert res2.updated_count == 1
    assert res2.accepted_count == 1

    with temp_db.connection() as conn:
        txn = conn.execute("SELECT * FROM transactions WHERE transaction_id = 'TXN-SNAP';").fetchone()
        assert txn["latest_version"] == 3
        assert txn["amount_minor"] == 3500


def test_late_lower_version_rejected(temp_db: DatabaseConnection, create_event_csv):
    """
    Verifies that when version 2 arrives after version 3 has been processed,
    the lower version is quarantined and does not overwrite current state.
    """
    service = PipelineService(temp_db)

    # Version 1 & Version 3 processed
    r1 = [{
        "event_id": "EVT-SEQ-1", "transaction_id": "TXN-OUT", "event_version": "1",
        "event_type": "CREATE", "event_timestamp": "2026-10-25T10:00:00Z",
        "business_date": "2026-10-25", "product_id": "PRD-0001", "customer_id": "CUST-0001",
        "amount_minor": "1000", "currency": "INR",
    }]
    r3 = [{
        "event_id": "EVT-SEQ-3", "transaction_id": "TXN-OUT", "event_version": "3",
        "event_type": "UPDATE", "event_timestamp": "2026-10-25T12:00:00Z",
        "business_date": "2026-10-25", "product_id": "PRD-0001", "customer_id": "CUST-0001",
        "amount_minor": "3000", "currency": "INR",
    }]
    service.run_pipeline(create_event_csv("out1.csv", r1))
    service.run_pipeline(create_event_csv("out3.csv", r3))

    # Version 2 arrives late
    r2 = [{
        "event_id": "EVT-SEQ-2", "transaction_id": "TXN-OUT", "event_version": "2",
        "event_type": "UPDATE", "event_timestamp": "2026-10-25T11:00:00Z",
        "business_date": "2026-10-25", "product_id": "PRD-0001", "customer_id": "CUST-0001",
        "amount_minor": "2000", "currency": "INR",
    }]
    res2 = service.run_pipeline(create_event_csv("out2_late.csv", r2))
    assert res2.rejected_count == 1
    assert res2.status == "PARTIAL"

    # Verify transaction state remains version 3 with amount 3000
    with temp_db.connection() as conn:
        txn = conn.execute("SELECT * FROM transactions WHERE transaction_id = 'TXN-OUT';").fetchone()
        assert txn["latest_version"] == 3
        assert txn["amount_minor"] == 3000


def test_conflicting_payload_on_same_transaction_version(temp_db: DatabaseConnection, create_event_csv):
    """
    Verifies that when an event with the same transaction_id and event_version
    arrives with a CONFLICTING payload, it is quarantined and not accepted as a duplicate.
    """
    service = PipelineService(temp_db)
    r1 = [{
        "event_id": "EVT-CONF-1", "transaction_id": "TXN-CONF", "event_version": "1",
        "event_type": "CREATE", "event_timestamp": "2026-10-25T10:00:00Z",
        "business_date": "2026-10-25", "product_id": "PRD-0001", "customer_id": "CUST-0001",
        "amount_minor": "10000", "currency": "INR",
    }]
    r2 = [{
        "event_id": "EVT-CONF-2", "transaction_id": "TXN-CONF", "event_version": "2",
        "event_type": "UPDATE", "event_timestamp": "2026-10-25T11:00:00Z",
        "business_date": "2026-10-25", "product_id": "PRD-0001", "customer_id": "CUST-0001",
        "amount_minor": "20000", "currency": "INR",
    }]
    service.run_pipeline(create_event_csv("conf_v1.csv", r1))
    service.run_pipeline(create_event_csv("conf_v2.csv", r2))

    # Now attempt a DIFFERENT event for version 2 (different event_id and conflicting amount 99999)
    r2_conflict = [{
        "event_id": "EVT-CONF-2-DIFF", "transaction_id": "TXN-CONF", "event_version": "2",
        "event_type": "UPDATE", "event_timestamp": "2026-10-25T11:30:00Z",
        "business_date": "2026-10-25", "product_id": "PRD-0001", "customer_id": "CUST-0001",
        "amount_minor": "99999", "currency": "INR",
    }]
    res = service.run_pipeline(create_event_csv("conf_v2_bad.csv", r2_conflict))
    assert res.rejected_count == 1
    assert res.status == "PARTIAL"

    with temp_db.connection() as conn:
        rej = conn.execute("SELECT * FROM rejected_records WHERE event_id = 'EVT-CONF-2-DIFF';").fetchone()
        assert rej is not None
        assert "Conflicting payload" in rej["rejection_reason"]

        # Authoritative state must still be 20000
        txn = conn.execute("SELECT * FROM transactions WHERE transaction_id = 'TXN-CONF';").fetchone()
        assert txn["amount_minor"] == 20000


def test_multiple_events_out_of_order_in_batch(temp_db: DatabaseConnection, create_event_csv):
    """
    Verifies that when CREATE v=1 and UPDATE v=2 arrive, but followed by late v=1 update attempt,
    the late lower version is rejected without corrupting the state.
    """
    service = PipelineService(temp_db)
    rows = [
        {
            "event_id": "EVT-ORD-1", "transaction_id": "TXN-ORD", "event_version": "1",
            "event_type": "CREATE", "event_timestamp": "2026-10-25T10:00:00Z",
            "business_date": "2026-10-25", "product_id": "PRD-0001", "customer_id": "CUST-0001",
            "amount_minor": "1000", "currency": "INR",
        },
        {
            "event_id": "EVT-ORD-3", "transaction_id": "TXN-ORD", "event_version": "3",
            "event_type": "UPDATE", "event_timestamp": "2026-10-25T12:00:00Z",
            "business_date": "2026-10-25", "product_id": "PRD-0001", "customer_id": "CUST-0001",
            "amount_minor": "3000", "currency": "INR",
        },
        {
            "event_id": "EVT-ORD-2", "transaction_id": "TXN-ORD", "event_version": "2",
            "event_type": "UPDATE", "event_timestamp": "2026-10-25T11:00:00Z",
            "business_date": "2026-10-25", "product_id": "PRD-0001", "customer_id": "CUST-0001",
            "amount_minor": "2000", "currency": "INR",
        },
    ]
    res = service.run_pipeline(create_event_csv("batch_out_of_order.csv", rows))
    assert res.accepted_count == 2
    assert res.rejected_count == 1
    assert res.status == "PARTIAL"

    with temp_db.connection() as conn:
        txn = conn.execute("SELECT * FROM transactions WHERE transaction_id = 'TXN-ORD';").fetchone()
        assert txn["latest_version"] == 3
        assert txn["amount_minor"] == 3000
