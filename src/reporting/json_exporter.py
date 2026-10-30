"""
JSON Run Report Exporter.
"""

import json
from pathlib import Path
from src.database.connection import DatabaseConnection, get_db
from src.config.settings import get_settings
from src.config.logging_config import get_logger

logger = get_logger(__name__)


def export_pipeline_run_json(
    run_id: str | None = None,
    db: DatabaseConnection | None = None,
    output_path: Path | None = None,
) -> Path:
    """Exports structured run report and operational details to JSON."""
    db = db or get_db()
    settings = get_settings()
    out_file = output_path or (settings.output_dir / "run_reports" / "pipeline_run_report.json")
    out_file.parent.mkdir(parents=True, exist_ok=True)

    with db.connection() as conn:
        if run_id:
            cur = conn.execute("SELECT * FROM pipeline_runs WHERE run_id = ?;", (run_id,))
        else:
            cur = conn.execute("SELECT * FROM pipeline_runs ORDER BY started_at DESC LIMIT 1;")
        run_row = cur.fetchone()

        if not run_row:
            report_data = {"error": "No pipeline runs found in database."}
        else:
            run_dict = dict(run_row)

            # Rejections breakdown
            rej_cur = conn.execute(
                """
                SELECT rejection_code, COUNT(*) AS count
                FROM rejected_records
                WHERE run_id = ?
                GROUP BY rejection_code;
                """,
                (run_dict["run_id"],),
            )
            rejections_by_code = {r["rejection_code"]: r["count"] for r in rej_cur.fetchall()}

            # Transaction totals
            txn_cur = conn.execute(
                """
                SELECT status, COUNT(*) AS count, COALESCE(SUM(amount_minor), 0) AS total_minor
                FROM transactions
                GROUP BY status;
                """
            )
            txn_summary = {r["status"]: {"count": r["count"], "total_minor": r["total_minor"]} for r in txn_cur.fetchall()}

            report_data = {
                "pipeline_run": run_dict,
                "rejections_breakdown": rejections_by_code,
                "authoritative_transactions": txn_summary,
            }

    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(report_data, f, indent=2)

    logger.info(f"Pipeline run JSON report written to {out_file}")
    return out_file
