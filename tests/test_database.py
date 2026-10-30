"""
Automated tests for database layer: initialization, constraints, foreign keys, indexes, migrations.
"""

import sqlite3
import pytest
from src.database.connection import DatabaseConnection
from src.database.schema import verify_database, EXPECTED_TABLES
from src.database.migrations import (
    ensure_migrations_table,
    get_current_version,
    record_migration,
    check_integrity,
)


def test_database_initialization(temp_db: DatabaseConnection):
    """Verifies that all 9 required tables exist after initialization."""
    assert verify_database(temp_db) is True
    with temp_db.connection() as conn:
        cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%';")
        tables = {row["name"] for row in cursor.fetchall()}
        for t in EXPECTED_TABLES:
            assert t in tables


def test_foreign_key_enforcement(temp_db: DatabaseConnection):
    """Verifies that foreign key violations raise an IntegrityError."""
    with temp_db.connection() as conn:
        # PRAGMA check
        fk = conn.execute("PRAGMA foreign_keys;").fetchone()[0]
        assert fk == 1

        # Attempt to insert transaction referencing non-existent product
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                """
                INSERT INTO transactions (
                    transaction_id, product_id, customer_id, business_date,
                    amount_minor, currency, status, latest_version, created_at, updated_at
                ) VALUES ('TXN-TEST', 'NON-EXISTENT-PRD', 'CUST-0001', '2026-10-25', 1000, 'INR', 'ACTIVE', 1, 'now', 'now');
                """
            )


def test_source_events_unique_version_constraint(temp_db: DatabaseConnection):
    """Verifies unique constraint on (transaction_id, event_version) in source_events."""
    with temp_db.transaction() as conn:
        # Create pipeline run first
        conn.execute(
            """
            INSERT INTO pipeline_runs (run_id, source_file, file_checksum, status, started_at)
            VALUES ('RUN-TEST', 'test.csv', 'hash123', 'RUNNING', '2026-10-25T10:00:00Z');
            """
        )
        conn.execute(
            """
            INSERT INTO source_events (
                event_id, transaction_id, event_version, event_type,
                event_timestamp, business_date, product_id, customer_id,
                amount_minor, currency, source_file, source_row_number,
                run_id, payload_hash, received_at
            ) VALUES (
                'EVT-1', 'TXN-1', 1, 'CREATE',
                '2026-10-25T10:00:00Z', '2026-10-25', 'PRD-0001', 'CUST-0001',
                5000, 'INR', 'test.csv', 2, 'RUN-TEST', 'hash1', '2026-10-25T10:00:00Z'
            );
            """
        )
        # Duplicate transaction_id + event_version
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                """
                INSERT INTO source_events (
                    event_id, transaction_id, event_version, event_type,
                    event_timestamp, business_date, product_id, customer_id,
                    amount_minor, currency, source_file, source_row_number,
                    run_id, payload_hash, received_at
                ) VALUES (
                    'EVT-2', 'TXN-1', 1, 'CREATE',
                    '2026-10-25T10:00:00Z', '2026-10-25', 'PRD-0001', 'CUST-0001',
                    5000, 'INR', 'test.csv', 3, 'RUN-TEST', 'hash2', '2026-10-25T10:00:00Z'
                );
                """
            )


def test_indexes_created(temp_db: DatabaseConnection):
    """Verifies that all performance indexes are present."""
    with temp_db.connection() as conn:
        cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='index';")
        indexes = {row["name"] for row in cursor.fetchall()}
        expected_indexes = [
            "idx_source_events_txn_id",
            "idx_source_events_txn_ver",
            "idx_source_events_biz_date",
            "idx_transactions_biz_prod",
            "idx_transactions_biz_cust",
            "idx_transactions_status",
            "idx_rejected_records_run_id",
            "idx_processed_files_checksum",
        ]
        for idx in expected_indexes:
            assert idx in indexes


def test_migrations_and_integrity_check(temp_db: DatabaseConnection):
    """Verifies migrations recording and database integrity checking."""
    ensure_migrations_table(temp_db)
    assert get_current_version(temp_db) == 0

    record_migration(temp_db, 1, "Initial V1 baseline")
    assert get_current_version(temp_db) == 1

    assert check_integrity(temp_db) is True
