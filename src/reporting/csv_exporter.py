"""
Formula-injection-safe CSV Exporters for all database tables and metrics.
"""

import csv
import sqlite3
from pathlib import Path
from src.database.connection import DatabaseConnection, get_db
from src.config.logging_config import get_logger

logger = get_logger(__name__)

# Dangerous prefixes for formula injection in spreadsheets (Excel/Sheets)
FORMULA_PREFIXES = ("=", "+", "-", "@", "\t", "\r")


def sanitize_cell_value(val: any) -> any:
    """
    Guards against CSV formula injection.
    Prefixes values starting with formula control characters with a single quote.
    """
    if val is None:
        return ""
    str_val = str(val)
    if str_val.startswith(FORMULA_PREFIXES):
        return f"'{str_val}"
    return str_val


def export_query_to_csv(
    conn: sqlite3.Connection,
    sql: str,
    output_path: Path,
    params: tuple = (),
) -> int:
    """
    Executes a SQL query and exports sanitized rows to CSV.
    Returns the count of exported rows.
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)
    cur = conn.execute(sql, params)
    rows = cur.fetchall()

    if not rows:
        # Write empty file with header if cursor has description
        col_names = [d[0] for d in cur.description] if cur.description else []
        with open(output_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            if col_names:
                writer.writerow(col_names)
        return 0

    col_names = [d[0] for d in cur.description]
    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(col_names)
        for row in rows:
            writer.writerow([sanitize_cell_value(row[col]) for col in col_names])

    logger.info(f"Exported {len(rows)} rows to {output_path}")
    return len(rows)


def export_all_tables_to_csv(
    db: DatabaseConnection | None = None,
    output_base_dir: Path | None = None,
) -> dict[str, Path]:
    """Exports all core metric, ledger, and run tables to their canonical output paths."""
    from src.config.settings import get_settings
    db = db or get_db()
    base_dir = output_base_dir or get_settings().output_dir

    outputs = {}
    with db.connection() as conn:
        # 1. Daily Product Metrics
        p_path = base_dir / "daily_product_metrics" / "daily_product_metrics.csv"
        export_query_to_csv(
            conn,
            "SELECT * FROM daily_product_metrics ORDER BY business_date DESC, product_id ASC;",
            p_path,
        )
        outputs["daily_product_metrics"] = p_path

        # 2. Daily Customer Metrics
        c_path = base_dir / "daily_customer_metrics" / "daily_customer_metrics.csv"
        export_query_to_csv(
            conn,
            "SELECT * FROM daily_customer_metrics ORDER BY business_date DESC, customer_id ASC;",
            c_path,
        )
        outputs["daily_customer_metrics"] = c_path

        # 3. Rejected Records
        r_path = base_dir / "rejected_records" / "rejected_records.csv"
        export_query_to_csv(
            conn,
            "SELECT * FROM rejected_records ORDER BY rejected_at DESC;",
            r_path,
        )
        outputs["rejected_records"] = r_path

        # 4. Pipeline Runs
        run_path = base_dir / "run_reports" / "pipeline_runs.csv"
        export_query_to_csv(
            conn,
            "SELECT * FROM pipeline_runs ORDER BY started_at DESC;",
            run_path,
        )
        outputs["pipeline_runs"] = run_path

        # 5. Transaction Summary
        txn_path = base_dir / "run_reports" / "transaction_summary.csv"
        export_query_to_csv(
            conn,
            """
            SELECT
                status,
                COUNT(*) AS count,
                COALESCE(SUM(amount_minor), 0) AS total_amount_minor,
                MIN(business_date) AS earliest_date,
                MAX(business_date) AS latest_date
            FROM transactions
            GROUP BY status;
            """,
            txn_path,
        )
        outputs["transaction_summary"] = txn_path

    return outputs
