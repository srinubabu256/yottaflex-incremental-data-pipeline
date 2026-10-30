"""
Database connection management for SQLite.
Ensures foreign key constraints, WAL mode, row factory, and transaction management.
"""

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Generator, Any
from src.config.settings import get_settings
from src.config.logging_config import get_logger

logger = get_logger(__name__)


class DatabaseConnection:
    """Manages SQLite database connections and transactions."""

    def __init__(self, db_path: Path | str | None = None, timeout: float = 30.0):
        if db_path is None:
            self.db_path = str(get_settings().database_path)
        else:
            self.db_path = str(db_path)
        self.timeout = timeout

    def get_raw_connection(self) -> sqlite3.Connection:
        """Creates a configured raw SQLite connection."""
        conn = sqlite3.connect(
            self.db_path,
            timeout=self.timeout,
            detect_types=sqlite3.PARSE_DECLTYPES,
        )
        conn.row_factory = sqlite3.Row

        # Crucial PRAGMAs
        conn.execute("PRAGMA foreign_keys = ON;")
        if self.db_path != ":memory:":
            conn.execute("PRAGMA journal_mode = WAL;")
            conn.execute("PRAGMA synchronous = NORMAL;")
            conn.execute("PRAGMA cache_size = -64000;")
            conn.execute("PRAGMA temp_store = MEMORY;")
        return conn

    @contextmanager
    def connection(self) -> Generator[sqlite3.Connection, None, None]:
        """Context manager for a standard connection."""
        conn = self.get_raw_connection()
        try:
            yield conn
        finally:
            conn.close()

    @contextmanager
    def transaction(self) -> Generator[sqlite3.Connection, None, None]:
        """
        Context manager for an atomic database transaction.
        Automatically commits on success or rolls back on exception.
        """
        conn = self.get_raw_connection()
        try:
            conn.execute("BEGIN IMMEDIATE;")
            yield conn
            conn.commit()
        except Exception as err:
            logger.error(f"Transaction failed, rolling back: {err}")
            conn.rollback()
            raise
        finally:
            conn.close()

    def execute(self, sql: str, params: tuple | dict | list = ()) -> list[sqlite3.Row]:
        """Executes a single query and returns fetched rows."""
        with self.connection() as conn:
            cursor = conn.cursor()
            cursor.execute(sql, params)
            return cursor.fetchall()

    def execute_script(self, script: str) -> None:
        """Executes a multi-statement SQL script."""
        with self.connection() as conn:
            conn.executescript(script)
            conn.commit()


# Default singleton manager
_default_db: DatabaseConnection | None = None


def get_db(db_path: Path | str | None = None) -> DatabaseConnection:
    """Factory function for obtaining a DatabaseConnection."""
    global _default_db
    if db_path is not None:
        return DatabaseConnection(db_path)
    if _default_db is None:
        _default_db = DatabaseConnection()
    return _default_db
