"""
Reconciliation report generation and CSV export.
"""

import csv
from pathlib import Path
from src.reconciliation.checks import ReconciliationCheckRow, perform_full_reconciliation
from src.database.connection import DatabaseConnection, get_db
from src.config.logging_config import get_logger

logger = get_logger(__name__)

RECONCILIATION_COLUMNS = [
    "metric_type",
    "business_date",
    "entity_id",
    "metric_name",
    "expected_value",
    "actual_value",
    "difference",
    "status",
    "explanation",
]


def generate_reconciliation_report(
    db: DatabaseConnection | None = None,
    output_path: Path | None = None,
) -> tuple[list[ReconciliationCheckRow], int, int]:
    """
    Executes all reconciliation checks and optionally writes results to CSV.
    Returns (check_rows, passed_count, failed_count).
    """
    db = db or get_db()
    with db.connection() as conn:
        checks = perform_full_reconciliation(conn)

    passed = sum(1 for c in checks if c.status == "PASS")
    failed = sum(1 for c in checks if c.status == "FAIL")

    if output_path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=RECONCILIATION_COLUMNS)
            writer.writeheader()
            for check in checks:
                writer.writerow(check.to_dict())
        logger.info(f"Reconciliation report saved to {output_path}")

    return checks, passed, failed
