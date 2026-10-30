"""
Performance benchmarking and metrics collection using time.perf_counter().
Records real, measured timing and throughput metrics for pipeline operations.
"""

import time
import csv
from dataclasses import dataclass
from pathlib import Path
from src.config.logging_config import get_logger

logger = get_logger(__name__)

PERFORMANCE_COLUMNS = [
    "dataset_label",
    "input_rows",
    "accepted_rows",
    "rejected_rows",
    "reading_time_seconds",
    "processing_time_seconds",
    "aggregation_time_seconds",
    "reconciliation_time_seconds",
    "total_runtime_seconds",
    "records_per_second",
]


@dataclass
class PerformanceBenchmarkResult:
    dataset_label: str
    input_rows: int
    accepted_rows: int
    rejected_rows: int
    reading_time_seconds: float
    processing_time_seconds: float
    aggregation_time_seconds: float
    reconciliation_time_seconds: float
    total_runtime_seconds: float
    records_per_second: float

    def to_dict(self) -> dict:
        return {
            "dataset_label": self.dataset_label,
            "input_rows": self.input_rows,
            "accepted_rows": self.accepted_rows,
            "rejected_rows": self.rejected_rows,
            "reading_time_seconds": round(self.reading_time_seconds, 4),
            "processing_time_seconds": round(self.processing_time_seconds, 4),
            "aggregation_time_seconds": round(self.aggregation_time_seconds, 4),
            "reconciliation_time_seconds": round(self.reconciliation_time_seconds, 4),
            "total_runtime_seconds": round(self.total_runtime_seconds, 4),
            "records_per_second": round(self.records_per_second, 2),
        }


def save_performance_report(
    results: list[PerformanceBenchmarkResult], output_file: Path
) -> None:
    """Writes performance benchmark results to CSV."""
    output_file.parent.mkdir(parents=True, exist_ok=True)
    with open(output_file, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=PERFORMANCE_COLUMNS)
        writer.writeheader()
        for r in results:
            writer.writerow(r.to_dict())
    logger.info(f"Performance report saved to {output_file}")
