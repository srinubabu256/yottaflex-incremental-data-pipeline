"""
Automated tests for late arriving events and historical partition assignment.
"""

from src.database.connection import DatabaseConnection
from src.processing.pipeline_runner import PipelineService


def test_late_event_assigned_to_business_date(temp_db: DatabaseConnection, create_event_csv):
    """
    Verifies that a late-arriving event is assigned strictly to its business_date,
    not the ingestion date, and updates the historical date's metrics.
    """
    service = PipelineService(temp_db)

    # Event occurred on Oct 10, ingested later (today)
    rows = [
        {
            "event_id": "EVT-LATE-1",
            "transaction_id": "TXN-LATE-1",
            "event_version": "1",
            "event_type": "CREATE",
            "event_timestamp": "2026-10-10T14:00:00Z",
            "business_date": "2026-10-10",  # Historical business date
            "product_id": "PRD-0001",
            "customer_id": "CUST-0001",
            "amount_minor": "45000",
            "currency": "INR",
        }
    ]
    csv_file = create_event_csv("late_event.csv", rows)
    res = service.run_pipeline(csv_file)
    assert res.inserted_count == 1
    assert res.status == "SUCCESS"

    with temp_db.connection() as conn:
        # Check that metric partition for 2026-10-10 was created
        metric = conn.execute(
            "SELECT * FROM daily_product_metrics WHERE business_date = '2026-10-10' AND product_id = 'PRD-0001';"
        ).fetchone()
        assert metric is not None
        assert metric["total_revenue_minor"] == 45000
        assert metric["transaction_count"] == 1

        # Confirm customer metric for 2026-10-10 was created
        c_metric = conn.execute(
            "SELECT * FROM daily_customer_metrics WHERE business_date = '2026-10-10' AND customer_id = 'CUST-0001';"
        ).fetchone()
        assert c_metric is not None
        assert c_metric["total_revenue_minor"] == 45000
