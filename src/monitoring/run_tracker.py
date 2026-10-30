"""
Pipeline run lifecycle tracking and observability.
"""

import sqlite3
import uuid
import time
from datetime import datetime, timezone
from typing import Optional

from src.config.constants import PipelineRunStatus
from src.database.models import PipelineRun
from src.config.logging_config import get_logger

logger = get_logger(__name__)


class RunTracker:
    """Manages recording of pipeline execution metadata and statuses."""

    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    def start_run(self, source_file: str, file_checksum: str) -> str:
        """Initializes a new pipeline run in RUNNING status."""
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
        run_id = f"RUN-{timestamp}-{uuid.uuid4().hex[:6]}"
        now_iso = datetime.now(timezone.utc).isoformat()

        self.conn.execute(
            """
            INSERT INTO pipeline_runs (
                run_id, source_file, file_checksum, status,
                started_at, completed_at, input_count, accepted_count,
                rejected_count, inserted_count, duplicate_count, updated_count,
                reversed_count, error_count, affected_period_count, duration_seconds,
                failure_reason
            ) VALUES (?, ?, ?, ?, ?, NULL, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0.0, NULL);
            """,
            (
                run_id,
                source_file,
                file_checksum,
                PipelineRunStatus.RUNNING.value,
                now_iso,
            ),
        )
        logger.info(f"Started pipeline run {run_id} for {source_file}")
        return run_id

    def complete_run(
        self,
        run_id: str,
        input_count: int,
        accepted_count: int,
        rejected_count: int,
        inserted_count: int,
        duplicate_count: int,
        updated_count: int,
        reversed_count: int,
        error_count: int,
        affected_period_count: int,
        duration_seconds: float,
    ) -> str:
        """
        Marks run as completed. If rejected_count > 0, status is PARTIAL;
        otherwise SUCCESS.
        """
        now_iso = datetime.now(timezone.utc).isoformat()
        status = (
            PipelineRunStatus.PARTIAL.value
            if rejected_count > 0
            else PipelineRunStatus.SUCCESS.value
        )

        self.conn.execute(
            """
            UPDATE pipeline_runs
            SET status = ?,
                completed_at = ?,
                input_count = ?,
                accepted_count = ?,
                rejected_count = ?,
                inserted_count = ?,
                duplicate_count = ?,
                updated_count = ?,
                reversed_count = ?,
                error_count = ?,
                affected_period_count = ?,
                duration_seconds = ?
            WHERE run_id = ?;
            """,
            (
                status,
                now_iso,
                input_count,
                accepted_count,
                rejected_count,
                inserted_count,
                duplicate_count,
                updated_count,
                reversed_count,
                error_count,
                affected_period_count,
                round(duration_seconds, 4),
                run_id,
            ),
        )
        logger.info(f"Completed run {run_id} with status {status} in {duration_seconds:.2f}s")
        return status

    def fail_run(self, run_id: str, reason: str, duration_seconds: float) -> None:
        """Marks run as FAILED with error explanation."""
        now_iso = datetime.now(timezone.utc).isoformat()
        self.conn.execute(
            """
            UPDATE pipeline_runs
            SET status = ?,
                completed_at = ?,
                duration_seconds = ?,
                failure_reason = ?
            WHERE run_id = ?;
            """,
            (
                PipelineRunStatus.FAILED.value,
                now_iso,
                round(duration_seconds, 4),
                reason,
                run_id,
            ),
        )
        logger.error(f"Failed run {run_id}: {reason}")

    def get_run(self, run_id: str) -> Optional[dict]:
        """Retrieves details of a specific pipeline run."""
        cur = self.conn.execute(
            "SELECT * FROM pipeline_runs WHERE run_id = ?;", (run_id,)
        )
        row = cur.fetchone()
        return dict(row) if row else None

    def list_runs(self, limit: int = 50) -> list[dict]:
        """Retrieves latest pipeline runs."""
        cur = self.conn.execute(
            "SELECT * FROM pipeline_runs ORDER BY started_at DESC LIMIT ?;", (limit,)
        )
        return [dict(row) for row in cur.fetchall()]
