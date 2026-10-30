"""
Pipeline Runner Service.
Orchestrates the complete end-to-end ingestion, validation, processing, aggregation,
and monitoring workflow in an isolated, reusable service.
"""

import time
import uuid
from pathlib import Path
from dataclasses import dataclass
from typing import Optional

from src.database.connection import DatabaseConnection, get_db
from src.ingestion.batch_loader import BatchLoader
from src.ingestion.csv_reader import IngestionError
from src.validation.schema_validator import validate_csv_schema, SchemaValidationError
from src.processing.idempotency import is_file_already_processed, record_processed_file
from src.processing.event_processor import EventProcessor
from src.processing.affected_periods import AffectedPeriodsTracker
from src.aggregation.recompute import recompute_affected_metrics
from src.monitoring.run_tracker import RunTracker
from src.monitoring.operational_metrics import OperationalSummary
from src.config.constants import PipelineRunStatus
from src.config.logging_config import get_logger

logger = get_logger(__name__)


@dataclass
class PipelineRunResult:
    """Structured result returned by the pipeline execution service."""
    run_id: str
    status: str
    source_file: str
    file_checksum: str
    input_count: int
    accepted_count: int
    rejected_count: int
    inserted_count: int
    duplicate_count: int
    updated_count: int
    reversed_count: int
    error_count: int
    affected_period_count: int
    duration_seconds: float
    is_idempotent_skip: bool = False
    failure_reason: Optional[str] = None
    reading_time_seconds: float = 0.0
    processing_time_seconds: float = 0.0
    aggregation_time_seconds: float = 0.0


class PipelineService:
    """Core service for executing the incremental data pipeline."""

    def __init__(self, db: DatabaseConnection | None = None):
        self.db = db or get_db()

    def run_pipeline(
        self,
        file_path: Path | str,
        batch_size: int = 5000,
    ) -> PipelineRunResult:
        """
        Executes the pipeline on the specified input CSV file.
        Returns a structured PipelineRunResult.
        """
        path = Path(file_path)
        start_time = time.perf_counter()

        if not path.exists():
            raise FileNotFoundError(f"Source file not found: {path}")

        # Compute file fingerprint
        loader = BatchLoader(path, batch_size=batch_size)
        try:
            file_checksum = loader.checksum
        except Exception as e:
            raise IngestionError(f"Failed to read file for fingerprinting: {e}") from e

        # Check file-level idempotency
        with self.db.connection() as conn:
            existing_file = is_file_already_processed(conn, file_checksum)
            if existing_file:
                logger.info(
                    f"File {path.name} (checksum {file_checksum[:8]}...) has already been successfully processed in run {existing_file['run_id']}. Skipping."
                )
                duration = time.perf_counter() - start_time
                return PipelineRunResult(
                    run_id=existing_file["run_id"],
                    status=PipelineRunStatus.SUCCESS.value,
                    source_file=str(path),
                    file_checksum=file_checksum,
                    input_count=0,
                    accepted_count=0,
                    rejected_count=0,
                    inserted_count=0,
                    duplicate_count=0,
                    updated_count=0,
                    reversed_count=0,
                    error_count=0,
                    affected_period_count=0,
                    duration_seconds=round(duration, 4),
                    is_idempotent_skip=True,
                )

        # Initialize run tracking
        run_id = ""
        with self.db.transaction() as conn:
            tracker = RunTracker(conn)
            run_id = tracker.start_run(str(path), file_checksum)

        total_input = 0
        total_accepted = 0
        total_rejected = 0
        total_inserted = 0
        total_duplicate = 0
        total_updated = 0
        total_reversed = 0
        total_errors = 0
        overall_affected = AffectedPeriodsTracker()
        total_reading_time = 0.0
        total_processing_time = 0.0
        total_aggregation_time = 0.0

        try:
            batch_iter = iter(loader.load_batches())
            headers_validated = False

            while True:
                t_r0 = time.perf_counter()
                try:
                    headers, batch_rows = next(batch_iter)
                except StopIteration:
                    total_reading_time += (time.perf_counter() - t_r0)
                    break
                total_reading_time += (time.perf_counter() - t_r0)

                if not headers_validated:
                    validate_csv_schema(headers)
                    headers_validated = True

                if not batch_rows:
                    continue

                # Process batch in an atomic database transaction
                with self.db.transaction() as conn:
                    processor = EventProcessor(conn, run_id, str(path))
                    t_p0 = time.perf_counter()
                    b_stats, b_affected = processor.process_batch(batch_rows)
                    total_processing_time += (time.perf_counter() - t_p0)

                    total_input += b_stats.input_count
                    total_accepted += b_stats.accepted_count
                    total_rejected += b_stats.rejected_count
                    total_inserted += b_stats.inserted_count
                    total_duplicate += b_stats.duplicate_count
                    total_updated += b_stats.updated_count
                    total_reversed += b_stats.reversed_count
                    total_errors += b_stats.error_count

                    # Targeted recomputation for affected groups within the transaction
                    t_a0 = time.perf_counter()
                    recompute_affected_metrics(conn, b_affected)
                    total_aggregation_time += (time.perf_counter() - t_a0)

                    for g in b_affected.product_groups:
                        overall_affected.product_groups.add(g)
                    for g in b_affected.customer_groups:
                        overall_affected.customer_groups.add(g)

            # If file was empty or only header, handle valid no-op
            duration = time.perf_counter() - start_time
            affected_count = overall_affected.total_affected_count()

            with self.db.transaction() as conn:
                tracker = RunTracker(conn)
                final_status = tracker.complete_run(
                    run_id=run_id,
                    input_count=total_input,
                    accepted_count=total_accepted,
                    rejected_count=total_rejected,
                    inserted_count=total_inserted,
                    duplicate_count=total_duplicate,
                    updated_count=total_updated,
                    reversed_count=total_reversed,
                    error_count=total_errors,
                    affected_period_count=affected_count,
                    duration_seconds=duration,
                )

                # Record in processed_files table
                file_id = f"FIL-{uuid.uuid4().hex[:10]}"
                from datetime import datetime, timezone
                now_iso = datetime.now(timezone.utc).isoformat()
                record_processed_file(
                    conn,
                    file_id=file_id,
                    source_file=str(path),
                    file_checksum=file_checksum,
                    run_id=run_id,
                    status=final_status,
                    processed_at=now_iso,
                )

            return PipelineRunResult(
                run_id=run_id,
                status=final_status,
                source_file=str(path),
                file_checksum=file_checksum,
                input_count=total_input,
                accepted_count=total_accepted,
                rejected_count=total_rejected,
                inserted_count=total_inserted,
                duplicate_count=total_duplicate,
                updated_count=total_updated,
                reversed_count=total_reversed,
                error_count=total_errors,
                affected_period_count=affected_count,
                duration_seconds=round(duration, 4),
                reading_time_seconds=round(total_reading_time, 4),
                processing_time_seconds=round(total_processing_time, 4),
                aggregation_time_seconds=round(total_aggregation_time, 4),
            )

        except Exception as e:
            duration = time.perf_counter() - start_time
            logger.error(f"Fatal error during pipeline run {run_id}: {e}", exc_info=True)
            with self.db.transaction() as conn:
                tracker = RunTracker(conn)
                tracker.fail_run(run_id, str(e), duration)

            return PipelineRunResult(
                run_id=run_id,
                status=PipelineRunStatus.FAILED.value,
                source_file=str(path),
                file_checksum=file_checksum,
                input_count=total_input,
                accepted_count=total_accepted,
                rejected_count=total_rejected,
                inserted_count=total_inserted,
                duplicate_count=total_duplicate,
                updated_count=total_updated,
                reversed_count=total_reversed,
                error_count=total_errors + 1,
                affected_period_count=0,
                duration_seconds=round(duration, 4),
                failure_reason=str(e),
            )
