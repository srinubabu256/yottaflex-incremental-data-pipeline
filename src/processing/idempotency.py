"""
File and event idempotency checking.
Ensures repeated executions and renamed files do not corrupt data.
"""

import sqlite3
from typing import Optional


def is_file_already_processed(conn: sqlite3.Connection, file_checksum: str) -> Optional[dict]:
    """
    Checks if a file with the given SHA-256 checksum has already been successfully processed.
    Returns the processed_files record if found, or None.
    """
    cur = conn.execute(
        """
        SELECT file_id, source_file, file_checksum, run_id, processing_status, processed_at
        FROM processed_files
        WHERE file_checksum = ? AND processing_status = 'SUCCESS';
        """,
        (file_checksum,),
    )
    row = cur.fetchone()
    if row:
        return dict(row)
    return None


def record_processed_file(
    conn: sqlite3.Connection,
    file_id: str,
    source_file: str,
    file_checksum: str,
    run_id: str,
    status: str,
    processed_at: str,
) -> None:
    """Records file processing status in processed_files table."""
    conn.execute(
        """
        INSERT INTO processed_files (file_id, source_file, file_checksum, run_id, processing_status, processed_at)
        VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT(file_checksum) DO UPDATE SET
            processing_status = excluded.processing_status,
            processed_at = excluded.processed_at,
            run_id = excluded.run_id;
        """,
        (file_id, source_file, file_checksum, run_id, status, processed_at),
    )


def check_event_idempotency(
    conn: sqlite3.Connection,
    event_id: str,
    transaction_id: str,
    event_version: int,
    payload_hash: str,
) -> tuple[bool, bool, str]:
    """
    Checks if the event already exists in source_events ledger.
    Returns:
        (is_duplicate, is_exact_match, explanation)
    """
    # 1. Check by event_id
    cur = conn.execute(
        "SELECT event_id, payload_hash, transaction_id, event_version FROM source_events WHERE event_id = ?;",
        (event_id,),
    )
    existing_by_id = cur.fetchone()
    if existing_by_id:
        if existing_by_id["payload_hash"] == payload_hash:
            return True, True, "Exact duplicate event_id with identical payload."
        return True, False, "Conflicting payload with identical event_id."

    # 2. Check by (transaction_id, event_version)
    cur = conn.execute(
        "SELECT event_id, payload_hash FROM source_events WHERE transaction_id = ? AND event_version = ?;",
        (transaction_id, event_version),
    )
    existing_by_ver = cur.fetchone()
    if existing_by_ver:
        if existing_by_ver["payload_hash"] == payload_hash:
            return True, True, f"Exact duplicate for transaction {transaction_id} version {event_version}."
        return True, False, f"Conflicting payload for transaction {transaction_id} version {event_version}."

    return False, False, ""
