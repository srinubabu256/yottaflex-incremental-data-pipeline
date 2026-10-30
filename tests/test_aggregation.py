"""
Automated tests for daily aggregation engines, partition shifts, and obsolete group cleanup.
"""

from src.database.connection import DatabaseConnection
from src.processing.pipeline_runner import PipelineService


def test_product_and_customer_aggregation(temp_db: DatabaseConnection, create_event_csv):
    """
    Verifies that daily product and customer aggregations calculate correct
    counts, totals, averages, and unique entities.
    """
    service = PipelineService(temp_db)
    # 2 transactions for same product, same date, 2 different customers
    # Txn 1: 10000, Txn 2: 30000 -> Total 40000, Avg 20000, distinct cust 2
    rows = [
        {
            "event_id": "EVT-AGG-1", "transaction_id": "TXN-AGG-1", "event_version": "1",
            "event_type": "CREATE", "event_timestamp": "2026-10-25T10:00:00Z",
            "business_date": "2026-10-25", "product_id": "PRD-0001", "customer_id": "CUST-0001",
            "amount_minor": "10000", "currency": "INR",
        },
        {
            "event_id": "EVT-AGG-2", "transaction_id": "TXN-AGG-2", "event_version": "1",
            "event_type": "CREATE", "event_timestamp": "2026-10-25T10:10:00Z",
            "business_date": "2026-10-25", "product_id": "PRD-0001", "customer_id": "CUST-0002",
            "amount_minor": "30000", "currency": "INR",
        },
    ]
    f = create_event_csv("agg_test.csv", rows)
    service.run_pipeline(f)

    with temp_db.connection() as conn:
        p_row = conn.execute(
            "SELECT * FROM daily_product_metrics WHERE business_date = '2026-10-25' AND product_id = 'PRD-0001';"
        ).fetchone()
        assert p_row["transaction_count"] == 2
        assert p_row["total_revenue_minor"] == 40000
        assert p_row["average_amount_minor"] == 20000
        assert p_row["customer_count"] == 2

        c_row = conn.execute(
            "SELECT * FROM daily_customer_metrics WHERE business_date = '2026-10-25' AND customer_id = 'CUST-0001';"
        ).fetchone()
        assert c_row["transaction_count"] == 1
        assert c_row["total_revenue_minor"] == 10000
        assert c_row["average_amount_minor"] == 10000
        assert c_row["product_count"] == 1


def test_obsolete_group_cleanup_when_all_transactions_reversed(temp_db: DatabaseConnection, create_event_csv):
    """
    Verifies that when all active transactions in a partition are reversed,
    the obsolete aggregate row is removed from daily_product_metrics.
    """
    service = PipelineService(temp_db)
    # Create single txn in partition
    r1 = [{
        "event_id": "EVT-OBS-1", "transaction_id": "TXN-OBS", "event_version": "1",
        "event_type": "CREATE", "event_timestamp": "2026-10-25T10:00:00Z",
        "business_date": "2026-10-25", "product_id": "PRD-0001", "customer_id": "CUST-0001",
        "amount_minor": "25000", "currency": "INR",
    }]
    service.run_pipeline(create_event_csv("obs_init.csv", r1))

    with temp_db.connection() as conn:
        assert conn.execute(
            "SELECT COUNT(*) FROM daily_product_metrics WHERE business_date = '2026-10-25' AND product_id = 'PRD-0001';"
        ).fetchone()[0] == 1

    # Reverse the single transaction
    r2 = [{
        "event_id": "EVT-OBS-2", "transaction_id": "TXN-OBS", "event_version": "2",
        "event_type": "REVERSE", "event_timestamp": "2026-10-25T12:00:00Z",
        "business_date": "2026-10-25", "product_id": "PRD-0001", "customer_id": "CUST-0001",
        "amount_minor": "25000", "currency": "INR",
    }]
    service.run_pipeline(create_event_csv("obs_rev.csv", r2))

    with temp_db.connection() as conn:
        # Obsolete group must be cleaned up (0 rows)
        count = conn.execute(
            "SELECT COUNT(*) FROM daily_product_metrics WHERE business_date = '2026-10-25' AND product_id = 'PRD-0001';"
        ).fetchone()[0]
        assert count == 0


def test_domain_edge_case_multi_hop_attribute_migration(temp_db: DatabaseConnection, create_event_csv):
    """
    Documented Domain-Specific Edge Case 1: Multi-Hop Attribute Migration.
    A transaction migrates across business_date, product_id, and customer_id simultaneously.
    Verifies that the old partition drops to zero / is removed, and the new partition is created.
    """
    service = PipelineService(temp_db)

    # Initial transaction in Group A: (2026-10-20, PRD-0001, CUST-0001)
    r1 = [{
        "event_id": "EVT-MIG-1", "transaction_id": "TXN-MIG", "event_version": "1",
        "event_type": "CREATE", "event_timestamp": "2026-10-20T10:00:00Z",
        "business_date": "2026-10-20", "product_id": "PRD-0001", "customer_id": "CUST-0001",
        "amount_minor": "50000", "currency": "INR",
    }]
    service.run_pipeline(create_event_csv("mig1.csv", r1))

    # Migrate simultaneously to Group B: (2026-10-22, PRD-0002, CUST-0002) with amount 60000
    r2 = [{
        "event_id": "EVT-MIG-2", "transaction_id": "TXN-MIG", "event_version": "2",
        "event_type": "UPDATE", "event_timestamp": "2026-10-22T10:00:00Z",
        "business_date": "2026-10-22", "product_id": "PRD-0002", "customer_id": "CUST-0002",
        "amount_minor": "60000", "currency": "INR",
    }]
    res2 = service.run_pipeline(create_event_csv("mig2.csv", r2))
    assert res2.updated_count == 1

    with temp_db.connection() as conn:
        # Old product group (2026-10-20, PRD-0001) must have been cleaned up
        old_prod = conn.execute(
            "SELECT COUNT(*) FROM daily_product_metrics WHERE business_date = '2026-10-20' AND product_id = 'PRD-0001';"
        ).fetchone()[0]
        assert old_prod == 0

        # Old customer group (2026-10-20, CUST-0001) must have been cleaned up
        old_cust = conn.execute(
            "SELECT COUNT(*) FROM daily_customer_metrics WHERE business_date = '2026-10-20' AND customer_id = 'CUST-0001';"
        ).fetchone()[0]
        assert old_cust == 0

        # New product group (2026-10-22, PRD-0002) must exist with 60000
        new_prod = conn.execute(
            "SELECT total_revenue_minor FROM daily_product_metrics WHERE business_date = '2026-10-22' AND product_id = 'PRD-0002';"
        ).fetchone()
        assert new_prod["total_revenue_minor"] == 60000

        # New customer group (2026-10-22, CUST-0002) must exist with 60000
        new_cust = conn.execute(
            "SELECT total_revenue_minor FROM daily_customer_metrics WHERE business_date = '2026-10-22' AND customer_id = 'CUST-0002';"
        ).fetchone()
        assert new_cust["total_revenue_minor"] == 60000
