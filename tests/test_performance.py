"""
Automated tests for performance benchmarking and metrics logging.
"""

from pathlib import Path
from src.reporting.performance_report import PerformanceBenchmarkResult, save_performance_report
from src.monitoring.operational_metrics import OperationalSummary


def test_performance_benchmark_result_structure(temp_dir: Path):
    """Verifies that performance results are properly formatted and written to CSV."""
    bench = PerformanceBenchmarkResult(
        dataset_label="Test_Benchmark_100_rows",
        input_rows=100,
        accepted_rows=98,
        rejected_rows=2,
        reading_time_seconds=0.0125,
        processing_time_seconds=0.0450,
        aggregation_time_seconds=0.0210,
        reconciliation_time_seconds=0.0150,
        total_runtime_seconds=0.0935,
        records_per_second=1069.52,
    )

    out_file = temp_dir / "perf_test.csv"
    save_performance_report([bench], out_file)
    assert out_file.exists()

    content = out_file.read_text(encoding="utf-8")
    assert "dataset_label" in content
    assert "Test_Benchmark_100_rows" in content
    assert "1069.52" in content


def test_operational_summary_calculation():
    """Verifies operational summary throughput and acceptance rate calculation."""
    summary = OperationalSummary.calculate(
        run_id="RUN-TEST",
        duration_seconds=0.5,
        total_records=1000,
        accepted_records=950,
        rejected_records=50,
    )
    assert summary.records_per_second == 2000.0
    assert summary.acceptance_rate_pct == 95.0
