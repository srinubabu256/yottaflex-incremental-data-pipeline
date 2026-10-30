"""
Automated tests for Command-Line Interface (CLI).
"""

import sys
from pathlib import Path
from unittest.mock import patch
from src.main import build_parser, main
from src.config.settings import get_settings


def test_cli_parser_subcommands():
    """Verifies all required subcommands are defined in the CLI parser."""
    parser = build_parser()
    subparsers_action = next(a for a in parser._actions if a.dest == "command")
    choices = subparsers_action.choices
    expected_cmds = [
        "init-db", "generate", "run", "reconcile", "report",
        "benchmark", "runs", "run-details", "rejects", "export"
    ]
    for cmd in expected_cmds:
        assert cmd in choices


def test_cli_init_db_execution(temp_dir: Path):
    """Verifies init-db CLI command execution."""
    test_db = temp_dir / "cli_init.db"
    with patch.object(get_settings(), "database_path", test_db):
        with patch.object(sys, "argv", ["main.py", "init-db"]):
            assert main() == 0
    assert test_db.exists()


def test_cli_generate_execution(temp_dir: Path):
    """Verifies generate CLI command execution."""
    out_file = temp_dir / "gen_cli.csv"
    with patch.object(sys, "argv", ["main.py", "generate", "--rows", "20", "--output", str(out_file)]):
        assert main() == 0
    assert out_file.exists()


def test_cli_runs_and_reconciliation_flow(temp_dir: Path):
    """Verifies full execution lifecycle in an isolated temporary database."""
    test_db = temp_dir / "cli_flow.db"
    with patch.object(get_settings(), "database_path", test_db):
        # 0. Init DB
        with patch.object(sys, "argv", ["main.py", "init-db"]):
            assert main() == 0

        # 1. Generate events
        ev_file = temp_dir / "cli_events.csv"
        with patch.object(sys, "argv", ["main.py", "generate", "--rows", "25", "--output", str(ev_file)]):
            assert main() == 0

        # 2. Run pipeline
        with patch.object(sys, "argv", ["main.py", "run", "--input", str(ev_file)]):
            assert main() == 0

        # 3. Runs list
        with patch.object(sys, "argv", ["main.py", "runs"]):
            assert main() == 0

        # 4. Reconcile
        with patch.object(sys, "argv", ["main.py", "reconcile"]):
            assert main() == 0

        # 5. Report
        with patch.object(sys, "argv", ["main.py", "report"]):
            assert main() == 0

        # 6. Rejects
        with patch.object(sys, "argv", ["main.py", "rejects"]):
            assert main() == 0

        # 7. Export
        export_dir = temp_dir / "exports"
        with patch.object(sys, "argv", ["main.py", "export", "--output", str(export_dir)]):
            assert main() == 0
        assert (export_dir / "daily_product_metrics" / "daily_product_metrics.csv").exists()


def test_cli_missing_input_file_returns_error():
    """Verifies that running pipeline with a non-existent file returns exit code 1."""
    with patch.object(sys, "argv", ["main.py", "run", "--input", "non_existent_file.csv"]):
        assert main() == 1
