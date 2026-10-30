"""
Authoritative transaction state management.
Maintains the latest state in the `transactions` table.
"""

import sqlite3
from typing import Optional
from src.config.constants import TransactionStatus


def get_current_transaction_state(
    conn: sqlite3.Connection, transaction_id: str
) -> Optional[dict]:
    """Retrieves current authoritative transaction state, if any."""
    cur = conn.execute(
        """
        SELECT transaction_id, product_id, customer_id, business_date,
               amount_minor, currency, status, latest_version, created_at, updated_at
        FROM transactions
        WHERE transaction_id = ?;
        """,
        (transaction_id,),
    )
    row = cur.fetchone()
    if row:
        return dict(row)
    return None


def apply_create_state(
    conn: sqlite3.Connection,
    transaction_id: str,
    product_id: str,
    customer_id: str,
    business_date: str,
    amount_minor: int,
    currency: str,
    version: int,
    received_at: str,
) -> None:
    """Inserts a new ACTIVE transaction state."""
    conn.execute(
        """
        INSERT INTO transactions (
            transaction_id, product_id, customer_id, business_date,
            amount_minor, currency, status, latest_version, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
        """,
        (
            transaction_id,
            product_id,
            customer_id,
            business_date,
            amount_minor,
            currency,
            TransactionStatus.ACTIVE.value,
            version,
            received_at,
            received_at,
        ),
    )


def apply_update_state(
    conn: sqlite3.Connection,
    transaction_id: str,
    product_id: str,
    customer_id: str,
    business_date: str,
    amount_minor: int,
    currency: str,
    version: int,
    received_at: str,
) -> None:
    """Updates an existing transaction to new values and version (remains ACTIVE)."""
    conn.execute(
        """
        UPDATE transactions
        SET product_id = ?,
            customer_id = ?,
            business_date = ?,
            amount_minor = ?,
            currency = ?,
            status = ?,
            latest_version = ?,
            updated_at = ?
        WHERE transaction_id = ?;
        """,
        (
            product_id,
            customer_id,
            business_date,
            amount_minor,
            currency,
            TransactionStatus.ACTIVE.value,
            version,
            received_at,
            transaction_id,
        ),
    )


def apply_reverse_state(
    conn: sqlite3.Connection,
    transaction_id: str,
    version: int,
    received_at: str,
) -> None:
    """Transitions a transaction to REVERSED status with updated version."""
    conn.execute(
        """
        UPDATE transactions
        SET status = ?,
            latest_version = ?,
            updated_at = ?
        WHERE transaction_id = ?;
        """,
        (
            TransactionStatus.REVERSED.value,
            version,
            received_at,
            transaction_id,
        ),
    )
