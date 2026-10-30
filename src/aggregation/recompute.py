"""
Targeted aggregate recomputation coordinator.
Applies recomputation exclusively to affected partitions.
"""

import sqlite3
from datetime import datetime, timezone
from src.processing.affected_periods import AffectedPeriodsTracker
from src.aggregation.product_metrics import recompute_product_metric
from src.aggregation.customer_metrics import recompute_customer_metric
from src.config.logging_config import get_logger

logger = get_logger(__name__)


def recompute_affected_metrics(
    conn: sqlite3.Connection,
    tracker: AffectedPeriodsTracker,
) -> tuple[int, int]:
    """
    Deterministically recalculates all affected (business_date, product_id)
    and (business_date, customer_id) partitions using high-throughput bulk SQL aggregation.
    Returns:
        (product_groups_processed, customer_groups_processed)
    """
    if tracker.total_affected_count() == 0:
        return 0, 0

    now_iso = datetime.now(timezone.utc).isoformat()
    prod_count = len(tracker.product_groups)
    cust_count = len(tracker.customer_groups)

    # 1. Product Metrics Bulk Recompute
    if tracker.product_groups:
        prod_dates = list({g[0] for g in tracker.product_groups})
        for i in range(0, len(prod_dates), 50):
            date_chunk = prod_dates[i : i + 50]
            placeholders = ",".join("?" for _ in date_chunk)
            cur = conn.execute(
                f"""
                SELECT business_date, product_id,
                       COUNT(*) AS txn_count,
                       COALESCE(SUM(amount_minor), 0) AS total_revenue,
                       COUNT(DISTINCT customer_id) AS cust_count
                FROM transactions
                WHERE status = 'ACTIVE' AND business_date IN ({placeholders})
                GROUP BY business_date, product_id;
                """,
                date_chunk,
            )
            active_map = {}
            for r in cur.fetchall():
                active_map[(r["business_date"], r["product_id"])] = (
                    r["txn_count"],
                    r["total_revenue"],
                    r["cust_count"],
                )

            chunk_set = set(date_chunk)
            upsert_rows = []
            delete_rows = []
            for b_date, p_id in tracker.product_groups:
                if b_date in chunk_set:
                    if (b_date, p_id) in active_map:
                        t_count, tot_rev, c_count = active_map[(b_date, p_id)]
                        avg_amt = tot_rev // t_count
                        upsert_rows.append((b_date, p_id, t_count, tot_rev, avg_amt, c_count, now_iso))
                    else:
                        delete_rows.append((b_date, p_id))

            if delete_rows:
                conn.executemany(
                    "DELETE FROM daily_product_metrics WHERE business_date = ? AND product_id = ?;",
                    delete_rows,
                )
            if upsert_rows:
                conn.executemany(
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
                    upsert_rows,
                )

    # 2. Customer Metrics Bulk Recompute
    if tracker.customer_groups:
        cust_dates = list({g[0] for g in tracker.customer_groups})
        for i in range(0, len(cust_dates), 50):
            date_chunk = cust_dates[i : i + 50]
            placeholders = ",".join("?" for _ in date_chunk)
            cur = conn.execute(
                f"""
                SELECT business_date, customer_id,
                       COUNT(*) AS txn_count,
                       COALESCE(SUM(amount_minor), 0) AS total_revenue,
                       COUNT(DISTINCT product_id) AS prod_count
                FROM transactions
                WHERE status = 'ACTIVE' AND business_date IN ({placeholders})
                GROUP BY business_date, customer_id;
                """,
                date_chunk,
            )
            active_map = {}
            for r in cur.fetchall():
                active_map[(r["business_date"], r["customer_id"])] = (
                    r["txn_count"],
                    r["total_revenue"],
                    r["prod_count"],
                )

            chunk_set = set(date_chunk)
            upsert_rows = []
            delete_rows = []
            for b_date, c_id in tracker.customer_groups:
                if b_date in chunk_set:
                    if (b_date, c_id) in active_map:
                        t_count, tot_rev, p_count = active_map[(b_date, c_id)]
                        avg_amt = tot_rev // t_count
                        upsert_rows.append((b_date, c_id, t_count, tot_rev, avg_amt, p_count, now_iso))
                    else:
                        delete_rows.append((b_date, c_id))

            if delete_rows:
                conn.executemany(
                    "DELETE FROM daily_customer_metrics WHERE business_date = ? AND customer_id = ?;",
                    delete_rows,
                )
            if upsert_rows:
                conn.executemany(
                    """
                    INSERT INTO daily_customer_metrics (
                        business_date, customer_id, transaction_count,
                        total_revenue_minor, average_amount_minor, product_count, last_recomputed_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(business_date, customer_id) DO UPDATE SET
                        transaction_count = excluded.transaction_count,
                        total_revenue_minor = excluded.total_revenue_minor,
                        average_amount_minor = excluded.average_amount_minor,
                        product_count = excluded.product_count,
                        last_recomputed_at = excluded.last_recomputed_at;
                    """,
                    upsert_rows,
                )

    logger.debug(
        f"Recomputed {prod_count} product metric partitions and {cust_count} customer metric partitions."
    )
    return prod_count, cust_count
