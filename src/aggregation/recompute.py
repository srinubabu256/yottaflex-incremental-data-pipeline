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
    and (business_date, customer_id) partitions.
    Returns:
        (product_groups_processed, customer_groups_processed)
    """
    now_iso = datetime.now(timezone.utc).isoformat()
    prod_count = 0
    cust_count = 0

    for biz_date, prod_id in tracker.product_groups:
        recompute_product_metric(conn, biz_date, prod_id, now_iso)
        prod_count += 1

    for biz_date, cust_id in tracker.customer_groups:
        recompute_customer_metric(conn, biz_date, cust_id, now_iso)
        cust_count += 1

    logger.debug(
        f"Recomputed {prod_count} product metric partitions and {cust_count} customer metric partitions."
    )
    return prod_count, cust_count
