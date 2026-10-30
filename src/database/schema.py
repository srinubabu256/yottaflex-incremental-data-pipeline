"""
Schema initialization and database verification.
"""

from pathlib import Path
import sqlite3
from src.database.connection import DatabaseConnection, get_db
from src.config.settings import get_settings
from src.config.logging_config import get_logger

logger = get_logger(__name__)

EXPECTED_TABLES = [
    "products",
    "customers",
    "pipeline_runs",
    "source_events",
    "transactions",
    "rejected_records",
    "daily_product_metrics",
    "daily_customer_metrics",
    "processed_files",
]


def init_db(db_path: Path | str | None = None, schema_file: Path | None = None) -> None:
    """
    Initializes the database schema using database/schema.sql.
    """
    settings = get_settings()
    target_schema_file = schema_file or settings.schema_sql_path

    if not target_schema_file.exists():
        raise FileNotFoundError(f"Schema file not found at: {target_schema_file}")

    with open(target_schema_file, "r", encoding="utf-8") as f:
        schema_sql = f.read()

    db = get_db(db_path)
    logger.info(f"Initializing database at: {db.db_path}")
    db.execute_script(schema_sql)
    logger.info("Database schema initialized successfully.")

    # Verify foreign key enforcement
    verify_database(db)


def verify_database(db: DatabaseConnection) -> bool:
    """
    Verifies that all required tables exist and foreign keys are active.
    """
    with db.connection() as conn:
        # Check foreign keys pragma
        fk_status = conn.execute("PRAGMA foreign_keys;").fetchone()
        if not fk_status or fk_status[0] != 1:
            raise RuntimeError("Database connection does not have foreign_keys enabled.")

        # Check tables
        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%';"
        )
        existing_tables = {row["name"] for row in cursor.fetchall()}

        missing_tables = set(EXPECTED_TABLES) - existing_tables
        if missing_tables:
            raise RuntimeError(f"Missing required tables in database: {missing_tables}")

    logger.debug("Database verification passed: all 9 tables present and foreign keys active.")
    return True
