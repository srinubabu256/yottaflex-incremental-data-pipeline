"""
Schema migration and integrity management.
"""

from src.database.connection import DatabaseConnection, get_db
from src.config.logging_config import get_logger

logger = get_logger(__name__)

CURRENT_SCHEMA_VERSION = 1


def ensure_migrations_table(db: DatabaseConnection) -> None:
    """Creates the schema_migrations table if it doesn't exist."""
    sql = """
    CREATE TABLE IF NOT EXISTS schema_migrations (
        version INTEGER PRIMARY KEY,
        applied_at TEXT NOT NULL,
        description TEXT NOT NULL
    );
    """
    with db.transaction() as conn:
        conn.execute(sql)


def get_current_version(db: DatabaseConnection) -> int:
    """Returns the current applied schema version."""
    ensure_migrations_table(db)
    with db.connection() as conn:
        cursor = conn.execute("SELECT MAX(version) FROM schema_migrations;")
        row = cursor.fetchone()
        return row[0] if row and row[0] is not None else 0


def record_migration(db: DatabaseConnection, version: int, description: str) -> None:
    """Records an applied migration."""
    from datetime import datetime, timezone
    now_iso = datetime.now(timezone.utc).isoformat()
    with db.transaction() as conn:
        conn.execute(
            "INSERT INTO schema_migrations (version, applied_at, description) VALUES (?, ?, ?);",
            (version, now_iso, description),
        )
    logger.info(f"Recorded migration version {version}: {description}")


def check_integrity(db: DatabaseConnection) -> bool:
    """Runs PRAGMA foreign_key_check and integrity_check."""
    with db.connection() as conn:
        integrity = conn.execute("PRAGMA integrity_check;").fetchall()
        if not integrity or integrity[0][0] != "ok":
            logger.error(f"Database integrity check failed: {integrity}")
            return False

        fk_violations = conn.execute("PRAGMA foreign_key_check;").fetchall()
        if fk_violations:
            logger.error(f"Foreign key violations found: {fk_violations}")
            return False

    return True
