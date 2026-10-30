"""
Direct calculation of expected ground-truth metrics from authoritative transactions.
"""

import sqlite3


def get_expected_product_metrics(conn: sqlite3.Connection) -> dict[tuple[str, str], dict]:
    """
    Computes expected daily product metrics directly from ACTIVE transactions.
    Returns mapping of (business_date, product_id) -> dict(metrics).
    """
    sql = """
        SELECT
            business_date,
            product_id,
            COUNT(*) AS expected_txn_count,
            COALESCE(SUM(amount_minor), 0) AS expected_revenue_minor,
            COUNT(DISTINCT customer_id) AS expected_customer_count
        FROM transactions
        WHERE status = 'ACTIVE'
        GROUP BY business_date, product_id;
    """
    cur = conn.execute(sql)
    results = {}
    for row in cur.fetchall():
        b_date = row["business_date"]
        p_id = row["product_id"]
        txn_cnt = row["expected_txn_count"]
        rev = row["expected_revenue_minor"]
        avg_amt = rev // txn_cnt if txn_cnt > 0 else 0
        cust_cnt = row["expected_customer_count"]

        results[(b_date, p_id)] = {
            "transaction_count": txn_cnt,
            "total_revenue_minor": rev,
            "average_amount_minor": avg_amt,
            "customer_count": cust_cnt,
        }
    return results


def get_expected_customer_metrics(conn: sqlite3.Connection) -> dict[tuple[str, str], dict]:
    """
    Computes expected daily customer metrics directly from ACTIVE transactions.
    Returns mapping of (business_date, customer_id) -> dict(metrics).
    """
    sql = """
        SELECT
            business_date,
            customer_id,
            COUNT(*) AS expected_txn_count,
            COALESCE(SUM(amount_minor), 0) AS expected_revenue_minor,
            COUNT(DISTINCT product_id) AS expected_product_count
        FROM transactions
        WHERE status = 'ACTIVE'
        GROUP BY business_date, customer_id;
    """
    cur = conn.execute(sql)
    results = {}
    for row in cur.fetchall():
        b_date = row["business_date"]
        c_id = row["customer_id"]
        txn_cnt = row["expected_txn_count"]
        rev = row["expected_revenue_minor"]
        avg_amt = rev // txn_cnt if txn_cnt > 0 else 0
        prod_cnt = row["expected_product_count"]

        results[(b_date, c_id)] = {
            "transaction_count": txn_cnt,
            "total_revenue_minor": rev,
            "average_amount_minor": avg_amt,
            "product_count": prod_cnt,
        }
    return results
