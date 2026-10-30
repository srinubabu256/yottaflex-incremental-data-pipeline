"""
Pytest configuration and fixtures.
Provides isolated temporary databases, test reference data, and CSV helpers.
"""

import csv
import pytest
from pathlib import Path
from src.database.connection import DatabaseConnection
from src.database.schema import init_db
from src.database.seed import seed_reference_data
from src.generator.reference_generator import save_reference_data
from src.config.constants import CANONICAL_COLUMNS


@pytest.fixture
def temp_dir(tmp_path: Path) -> Path:
    """Provides a clean temporary directory for files."""
    return tmp_path


@pytest.fixture
def temp_db(tmp_path: Path) -> DatabaseConnection:
    """
    Creates an isolated temporary SQLite database with all 9 tables,
    indexes, and seeded products and customers.
    """
    db_file = tmp_path / "test_pipeline.db"
    db = DatabaseConnection(db_file)

    # Initialize schema
    schema_sql_path = Path(__file__).resolve().parent.parent / "database" / "schema.sql"
    init_db(db_file, schema_file=schema_sql_path)

    # Generate and seed reference data
    ref_dir = tmp_path / "reference"
    prod_csv, cust_csv = save_reference_data(ref_dir, product_count=20, customer_count=40, seed=42)
    seed_reference_data(db, prod_csv, cust_csv)

    return db


@pytest.fixture
def create_event_csv(temp_dir: Path):
    """Factory fixture to create sample CSV event files quickly."""
    def _create(filename: str, rows: list[dict[str, str]], columns: list[str] | None = None) -> Path:
        cols = columns if columns is not None else CANONICAL_COLUMNS
        file_path = temp_dir / filename
        file_path.parent.mkdir(parents=True, exist_ok=True)
        with open(file_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=cols)
            writer.writeheader()
            writer.writerows(rows)
        return file_path
    return _create
