"""
Daily product aggregation recomputation.
Calculates revenue, transaction count, average transaction amount, and distinct customer reach.
Only ACTIVE transactions contribute.
"""

import sqlite3
from src.config.logging_config import get_logger

logger = get_logger(__name__)


def recompute_product_metric(
    conn: sqlite3.Connection,
    business_date: str,
    product_id: str,
    recomputed_at: str,
) -> bool:
    """
    Recomputes daily_product_metrics for a specific (business_date, product_id) partition.
    If no active transactions remain, deletes the obsolete aggregate record.
    Returns True if an active record was inserted/updated, False if deleted/empty.
    """
    query = """
        SELECT
            COUNT(*) AS txn_count,
            COALESCE(SUM(amount_minor), 0) AS total_revenue,
            COUNT(DISTINCT customer_id) AS cust_count
        FROM transactions
        WHERE business_date = ?
          AND product_id = ?
          AND status = 'ACTIVE';
    """
    row = conn.execute(query, (business_date, product_id)).fetchone()
    txn_count = row["txn_count"] if row else 0

    if txn_count == 0:
        # Obsolete group cleanup: remove when no active transactions remain
        conn.execute(
            "DELETE FROM daily_product_metrics WHERE business_date = ? AND product_id = ?;",
            (business_date, product_id),
        )
        return False

    total_revenue = row["total_revenue"]
    cust_count = row["cust_count"]
    avg_amount = total_revenue // txn_count  # Integer division for minor units

    conn.execute(
        """
        INSERT INTO daily_product_metrics (
            business_date, product_id, transaction_count,
            total_revenue_minor, average_amount_minor, customer_count, last_recomputed_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(business_date, product_id) DO UPDATE SET
            transaction_count = excluded.transaction_count,
            total_revenue_minor = excluded.total_revenue_minor,
            average_amount_minor = excluded.average_amount_minor,
            customer_count = excluded.customer_count,
            last_recomputed_at = excluded.last_recomputed_at;
        """,
        (
            business_date,
            product_id,
            txn_count,
            total_revenue,
            avg_amount,
            cust_count,
            recomputed_at,
        ),
    )
    return True
