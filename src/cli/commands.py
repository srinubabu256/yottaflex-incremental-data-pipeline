"""
CLI command implementations for YottaFlex Data Pipeline.
"""

import sys
import time
from pathlib import Path
from tabulate import tabulate

from src.config.settings import get_settings
from src.config.logging_config import configure_logging, get_logger
from src.database.schema import init_db
from src.database.seed import seed_reference_data
from src.database.connection import get_db, DatabaseConnection
import uuid
from src.generator.reference_generator import save_reference_data
from src.generator.event_generator import SyntheticEventGenerator
from src.generator.scenarios import generate_all_scenarios
from src.processing.pipeline_runner import PipelineService
from src.reconciliation.report import generate_reconciliation_report
from src.reporting.csv_exporter import export_all_tables_to_csv
from src.reporting.json_exporter import export_pipeline_run_json
from src.reporting.performance_report import (
    PerformanceBenchmarkResult,
    save_performance_report,
)
from src.monitoring.run_tracker import RunTracker

logger = get_logger(__name__)


def handle_init_db(args) -> int:
    """Initializes the database schema and seeds reference data."""
    settings = get_settings()
    try:
        init_db(settings.database_path, settings.schema_sql_path)

        # Generate reference CSVs if they don't exist
        ref_dir = settings.reference_data_dir
        if not (ref_dir / "products.csv").exists() or not (ref_dir / "customers.csv").exists():
            save_reference_data(ref_dir, product_count=50, customer_count=100, seed=42)

        p_count, c_count = seed_reference_data(get_db(), ref_dir / "products.csv", ref_dir / "customers.csv")
        print(f"Database successfully initialized at {settings.database_path}")
        print(f"Seeded {p_count} products and {c_count} customers from reference data.")
        return 0
    except Exception as e:
        logger.error(f"Failed to initialize database: {e}", exc_info=True)
        print(f"Error: {e}", file=sys.stderr)
        return 1


def handle_generate(args) -> int:
    """Generates synthetic dataset or standard sample scenarios."""
    settings = get_settings()
    rows = getattr(args, "rows", 100)
    seed = getattr(args, "seed", 42)
    output_path = getattr(args, "output", None)

    try:
        # Also ensure reference data exists
        ref_dir = settings.reference_data_dir
        save_reference_data(ref_dir, product_count=50, customer_count=100, seed=seed)

        # Generate curated sample scenarios in data/sample/
        base_sample_dir = settings.reference_data_dir.parent / "sample"
        generate_all_scenarios(base_sample_dir, seed=seed)

        # Generate target event file
        gen = SyntheticEventGenerator(seed=seed)
        target_file = Path(output_path) if output_path else (settings.reference_data_dir.parent / "generated" / "events.csv")
        events = gen.generate_events(
            total_events=rows,
            update_ratio=0.15,
            reverse_ratio=0.05,
            late_ratio=0.05,
            invalid_ratio=0.02 if rows >= 100 else 0.0,
        )
        gen.write_events_to_csv(target_file, events)

        print(f"Generated {len(events)} events (seed={seed}) to {target_file}")
        print(f"Generated sample scenario suites into {base_sample_dir}")
        return 0
    except Exception as e:
        logger.error(f"Failed to generate synthetic data: {e}", exc_info=True)
        print(f"Error: {e}", file=sys.stderr)
        return 1


def handle_run(args) -> int:
    """Executes the pipeline on an input CSV file."""
    input_file = Path(args.input)
    batch_size = getattr(args, "batch_size", 5000) or 5000

    if not input_file.exists():
        print(f"Error: Input file does not exist: {input_file}", file=sys.stderr)
        return 1

    try:
        service = PipelineService()
        result = service.run_pipeline(input_file, batch_size=batch_size)

        table_data = [
            ["Run ID", result.run_id],
            ["Status", result.status],
            ["Source File", result.source_file],
            ["File Checksum", f"{result.file_checksum[:16]}..."],
            ["Idempotent Skip", "Yes" if result.is_idempotent_skip else "No"],
            ["Input Rows", result.input_count],
            ["Accepted Rows", result.accepted_count],
            ["Rejected Rows", result.rejected_count],
            ["Inserted Events", result.inserted_count],
            ["Duplicate Events", result.duplicate_count],
            ["Applied Updates", result.updated_count],
            ["Applied Reversals", result.reversed_count],
            ["Affected Partitions", result.affected_period_count],
            ["Duration (seconds)", f"{result.duration_seconds:.4f}"],
        ]
        if result.failure_reason:
            table_data.append(["Failure Reason", result.failure_reason])

        print(tabulate(table_data, headers=["Metric", "Value"], tablefmt="grid"))
        return 0 if result.status in {"SUCCESS", "PARTIAL"} else 1
    except Exception as e:
        logger.error(f"Execution failed: {e}", exc_info=True)
        print(f"Error: {e}", file=sys.stderr)
        return 1


def handle_reconcile(args) -> int:
    """Runs independent reconciliation checks."""
    settings = get_settings()
    out_file = settings.output_dir / "reconciliation" / "reconciliation_report.csv"

    try:
        checks, passed, failed = generate_reconciliation_report(output_path=out_file)
        summary = [
            ["Total Checks", len(checks)],
            ["Passed Checks", passed],
            ["Failed Checks", failed],
            ["Reconciliation Status", "PASS" if failed == 0 and len(checks) > 0 else ("FAIL" if failed > 0 else "NO_DATA")],
            ["Report File", str(out_file)],
        ]
        print(tabulate(summary, headers=["Metric", "Value"], tablefmt="grid"))

        if failed > 0:
            failures = [c.to_dict() for c in checks if c.status == "FAIL"]
            print("\nFailures Detail:")
            print(tabulate(failures, headers="keys", tablefmt="simple"))
            return 1
        return 0
    except Exception as e:
        logger.error(f"Reconciliation error: {e}", exc_info=True)
        print(f"Error: {e}", file=sys.stderr)
        return 1


def handle_report(args) -> int:
    """Generates all standard reports (CSV, JSON, Reconciliation)."""
    settings = get_settings()
    try:
        # Export CSVs
        csv_files = export_all_tables_to_csv()
        # Export JSON run report
        json_file = export_pipeline_run_json()
        # Run reconciliation report
        recon_path = settings.output_dir / "reconciliation" / "reconciliation_report.csv"
        _, passed, failed = generate_reconciliation_report(output_path=recon_path)

        table_data = [
            ["Daily Product Metrics", str(csv_files["daily_product_metrics"])],
            ["Daily Customer Metrics", str(csv_files["daily_customer_metrics"])],
            ["Rejected Records", str(csv_files["rejected_records"])],
            ["Pipeline Runs", str(csv_files["pipeline_runs"])],
            ["Transaction Summary", str(csv_files["transaction_summary"])],
            ["Pipeline Run JSON", str(json_file)],
            ["Reconciliation Report", str(recon_path)],
        ]
        print("Generated Output Reports:")
        print(tabulate(table_data, headers=["Report Type", "File Path"], tablefmt="grid"))
        return 0
    except Exception as e:
        logger.error(f"Failed to generate reports: {e}", exc_info=True)
        print(f"Error: {e}", file=sys.stderr)
        return 1


def handle_benchmark(args) -> int:
    """Executes performance benchmark with actual timing using time.perf_counter()."""
    rows = getattr(args, "rows", 100000) or 100000
    seed = getattr(args, "seed", 42) or 42
    settings = get_settings()

    print(f"Starting actual performance benchmark for {rows} records (seed={seed})...")

    # Generate synthetic file for benchmark
    bench_dir = settings.reference_data_dir.parent / "generated"
    bench_file = bench_dir / f"benchmark_{rows}.csv"
    gen = SyntheticEventGenerator(seed=seed)

    t0 = time.perf_counter()
    events = gen.generate_events(
        total_events=rows,
        update_ratio=0.15,
        reverse_ratio=0.05,
        late_ratio=0.05,
        invalid_ratio=0.01,
    )
    gen.write_events_to_csv(bench_file, events)
    gen_time = time.perf_counter() - t0
    print(f"Generated {rows} benchmark events in {gen_time:.2f}s")

    # Use isolated database for benchmarking to ensure pure, accurate fresh measurements
    bench_db_file = settings.database_path.parent / f"bench_temp_{uuid.uuid4().hex[:6]}.db"
    init_db(bench_db_file, settings.schema_sql_path)
    bench_db = DatabaseConnection(bench_db_file)
    seed_reference_data(bench_db)

    # Run pipeline and measure
    t_pipeline_start = time.perf_counter()
    service = PipelineService(bench_db)
    result = service.run_pipeline(bench_file, batch_size=5000)
    pipeline_duration = time.perf_counter() - t_pipeline_start

    # Run reconciliation and measure
    t_recon_start = time.perf_counter()
    checks, passed, failed = generate_reconciliation_report(db=bench_db)
    recon_duration = time.perf_counter() - t_recon_start

    db_size_mb = (bench_db_file.stat().st_size / (1024 * 1024)) if bench_db_file.exists() else 0.0

    total_time = pipeline_duration + recon_duration
    rps = rows / pipeline_duration if pipeline_duration > 0 else 0.0

    bench_result = PerformanceBenchmarkResult(
        dataset_label=f"Benchmark_{rows}_rows",
        input_rows=result.input_count,
        accepted_rows=result.accepted_count,
        rejected_rows=result.rejected_count,
        reading_time_seconds=result.reading_time_seconds,
        processing_time_seconds=result.processing_time_seconds,
        aggregation_time_seconds=result.aggregation_time_seconds,
        reconciliation_time_seconds=recon_duration,
        total_runtime_seconds=total_time,
        records_per_second=rps,
    )

    out_csv = settings.output_dir / "performance" / "performance_report.csv"
    save_performance_report([bench_result], out_csv)

    # Cleanup isolated benchmark DB
    del service
    del bench_db
    if bench_db_file.exists():
        try: bench_db_file.unlink()
        except: pass
    for extra in settings.database_path.parent.glob(f"{bench_db_file.stem}*"):
        try: extra.unlink()
        except: pass

    table_data = [
        ["Total Rows", result.input_count],
        ["Accepted Rows", result.accepted_count],
        ["Rejected Rows", result.rejected_count],
        ["CSV Reading Time (sec)", f"{result.reading_time_seconds:.4f}"],
        ["Processing Time (sec)", f"{result.processing_time_seconds:.4f}"],
        ["Aggregation Time (sec)", f"{result.aggregation_time_seconds:.4f}"],
        ["Pipeline Runtime (sec)", f"{pipeline_duration:.4f}"],
        ["Reconciliation Time (sec)", f"{recon_duration:.4f}"],
        ["Total Runtime (sec)", f"{total_time:.4f}"],
        ["Throughput (rows/sec)", f"{rps:.2f}"],
        ["Database Size (MB)", f"{db_size_mb:.2f} MB"],
        ["Reconciliation Result", f"{passed} PASS, {failed} FAIL"],
        ["Benchmark Report Path", str(out_csv)],
    ]
    print("\nBenchmark Execution Results:")
    print(tabulate(table_data, headers=["Metric", "Measured Value"], tablefmt="grid"))
    return 0


def handle_runs(args) -> int:
    """Lists recent pipeline runs."""
    limit = getattr(args, "limit", 20) or 20
    with get_db().connection() as conn:
        tracker = RunTracker(conn)
        runs = tracker.list_runs(limit=limit)

    if not runs:
        print("No pipeline runs found.")
        return 0

    display_data = [
        [
            r["run_id"],
            r["status"],
            Path(r["source_file"]).name,
            r["input_count"],
            r["accepted_count"],
            r["rejected_count"],
            f"{r['duration_seconds']:.2f}s",
            r["started_at"],
        ]
        for r in runs
    ]
    print(tabulate(
        display_data,
        headers=["Run ID", "Status", "File", "Input", "Accepted", "Rejected", "Duration", "Started At"],
        tablefmt="grid",
    ))
    return 0


def handle_run_details(args) -> int:
    """Displays detailed metrics for a specific pipeline run."""
    run_id = args.run_id
    with get_db().connection() as conn:
        tracker = RunTracker(conn)
        run = tracker.get_run(run_id)

    if not run:
        print(f"Pipeline run '{run_id}' not found.", file=sys.stderr)
        return 1

    table_data = [[k, v] for k, v in run.items()]
    print(tabulate(table_data, headers=["Field", "Value"], tablefmt="grid"))
    return 0


def handle_rejects(args) -> int:
    """Lists quarantined rejected records."""
    run_id = getattr(args, "run_id", None)
    limit = getattr(args, "limit", 50) or 50

    with get_db().connection() as conn:
        if run_id:
            cur = conn.execute(
                "SELECT * FROM rejected_records WHERE run_id = ? ORDER BY source_row_number ASC LIMIT ?;",
                (run_id, limit),
            )
        else:
            cur = conn.execute(
                "SELECT * FROM rejected_records ORDER BY rejected_at DESC LIMIT ?;",
                (limit,),
            )
        rows = cur.fetchall()

    if not rows:
        print("No rejected records found.")
        return 0

    table_data = [
        [
            r["reject_id"],
            r["run_id"],
            r["source_row_number"],
            r["event_id"],
            r["rejection_code"],
            r["rejection_reason"][:60],
        ]
        for r in rows
    ]
    print(tabulate(
        table_data,
        headers=["Reject ID", "Run ID", "Row #", "Event ID", "Code", "Reason"],
        tablefmt="grid",
    ))
    return 0


def handle_export(args) -> int:
    """Exports all database tables to CSV format."""
    out_dir = Path(args.output) if getattr(args, "output", None) else None
    try:
        files = export_all_tables_to_csv(output_base_dir=out_dir)
        table_data = [[k, str(v)] for k, v in files.items()]
        print("Exported Tables:")
        print(tabulate(table_data, headers=["Table / Metric", "CSV Destination"], tablefmt="grid"))
        return 0
    except Exception as e:
        logger.error(f"Export failed: {e}", exc_info=True)
        print(f"Error: {e}", file=sys.stderr)
        return 1
