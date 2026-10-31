"""
Main entry point for YottaFlex Data Pipeline CLI.
"""

import argparse
import sys
from src.config.logging_config import configure_logging
from src.cli.commands import (
    handle_init_db,
    handle_generate,
    handle_run,
    handle_reconcile,
    handle_report,
    handle_benchmark,
    handle_runs,
    handle_run_details,
    handle_rejects,
    handle_export,
)


def build_parser() -> argparse.ArgumentParser:
    """Builds and configures the CLI argument parser."""
    parser = argparse.ArgumentParser(
        prog="python -m src.main",
        description="YottaFlex - Production-grade Incremental Data Engineering Pipeline",
    )
    parser.add_argument(
        "--log-level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        default="INFO",
        help="Logging verbosity level (default: INFO)",
    )

    subparsers = parser.add_subparsers(dest="command", help="Available subcommands")

    # 1. init-db
    init_parser = subparsers.add_parser("init-db", help="Initialize database schema and seed reference data")
    init_parser.add_argument("--reset", action="store_true", help="Reset/drop existing database before initializing")

    # 2. generate
    gen_parser = subparsers.add_parser("generate", help="Generate synthetic transaction events")
    gen_parser.add_argument("--rows", type=int, default=100, help="Number of event rows to generate (default: 100)")
    gen_parser.add_argument("--seed", type=int, default=42, help="Random seed for reproducibility (default: 42)")
    gen_parser.add_argument("--output", type=str, default=None, help="Output CSV path")

    # 3. run
    run_parser = subparsers.add_parser("run", help="Execute the pipeline on an input CSV")
    run_parser.add_argument("--input", type=str, required=True, help="Path to input event CSV file")
    run_parser.add_argument("--batch-size", type=int, default=5000, help="Batch size for processing (default: 5000)")

    # 4. reconcile
    subparsers.add_parser("reconcile", help="Run independent reconciliation between aggregates and transactions")

    # 5. report
    subparsers.add_parser("report", help="Generate all standard CSV and JSON reports")

    # 6. benchmark
    bench_parser = subparsers.add_parser("benchmark", help="Run performance benchmark with high-resolution timer")
    bench_parser.add_argument("--rows", type=int, default=100000, help="Number of rows for benchmark (default: 100000)")
    bench_parser.add_argument("--seed", type=int, default=42, help="Random seed (default: 42)")

    # 7. runs
    runs_parser = subparsers.add_parser("runs", help="List recent pipeline execution runs")
    runs_parser.add_argument("--limit", type=int, default=20, help="Maximum runs to display")

    # 8. run-details
    details_parser = subparsers.add_parser("run-details", help="Display details for a specific run")
    details_parser.add_argument("--run-id", type=str, required=True, help="Pipeline Run ID")

    # 9. rejects
    rejects_parser = subparsers.add_parser("rejects", help="List quarantined rejected records")
    rejects_parser.add_argument("--run-id", type=str, default=None, help="Filter rejections by run ID")
    rejects_parser.add_argument("--limit", type=int, default=50, help="Maximum rejected records to display")

    # 10. export
    export_parser = subparsers.add_parser("export", help="Export all database tables to CSV format")
    export_parser.add_argument("--output", type=str, default="outputs", help="Base output directory")

    return parser


def main() -> int:
    """Main execution function."""
    parser = build_parser()
    args = parser.parse_args()

    configure_logging(log_level=args.log_level)

    if not args.command:
        parser.print_help()
        return 0

    command_handlers = {
        "init-db": handle_init_db,
        "generate": handle_generate,
        "run": handle_run,
        "reconcile": handle_reconcile,
        "report": handle_report,
        "benchmark": handle_benchmark,
        "runs": handle_runs,
        "run-details": handle_run_details,
        "rejects": handle_rejects,
        "export": handle_export,
    }

    handler = command_handlers.get(args.command)
    if handler:
        try:
            return handler(args)
        except KeyboardInterrupt:
            print("\nExecution interrupted by user.", file=sys.stderr)
            return 130
        except Exception as e:
            print(f"Error: {e}", file=sys.stderr)
            return 1
    else:
        parser.print_help()
        return 1


if __name__ == "__main__":
    sys.exit(main())
