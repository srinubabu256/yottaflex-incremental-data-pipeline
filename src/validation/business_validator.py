"""
Business rules and transaction state validation.
"""

import sqlite3
from typing import Optional
from src.config.constants import EventType, RejectionCode, TransactionStatus
from src.validation.validation_result import ValidationResult


class BusinessValidator:
    """Validates relational references, event sequencing, and transaction states."""

    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn
        self._products_cache: set[str] | None = None
        self._customers_cache: set[str] | None = None

    def _get_products(self) -> set[str]:
        if self._products_cache is None:
            cur = self.conn.execute("SELECT product_id FROM products;")
            self._products_cache = {row[0] for row in cur.fetchall()}
        return self._products_cache

    def _get_customers(self) -> set[str]:
        if self._customers_cache is None:
            cur = self.conn.execute("SELECT customer_id FROM customers;")
            self._customers_cache = {row[0] for row in cur.fetchall()}
        return self._customers_cache

    def validate_business_rules(
        self,
        row_number: int,
        record: dict,
        active_batch_txns: dict[str, dict] | None = None,
    ) -> ValidationResult:
        """
        Validates product existence, customer existence, and transaction sequence validity.
        active_batch_txns can be passed to account for intra-batch transitions.
        """
        raw_payload = record
        event_id = record["event_id"]
        txn_id = record["transaction_id"]
        ev_type = record["event_type"]
        ev_ver = record["event_version"]
        prod_id = record["product_id"]
        cust_id = record["customer_id"]

        # 1. Product existence
        if prod_id not in self._get_products():
            return ValidationResult.fail(
                row_number=row_number,
                code=RejectionCode.UNKNOWN_PRODUCT,
                reason=f"Product '{prod_id}' does not exist in reference catalog.",
                raw_payload=raw_payload,
                event_id=event_id,
            )

        # 2. Customer existence
        if cust_id not in self._get_customers():
            return ValidationResult.fail(
                row_number=row_number,
                code=RejectionCode.UNKNOWN_CUSTOMER,
                reason=f"Customer '{cust_id}' does not exist in reference catalog.",
                raw_payload=raw_payload,
                event_id=event_id,
            )

        # 3. Check current transaction state (from DB or intra-batch state)
        current_state = None
        if active_batch_txns and txn_id in active_batch_txns:
            current_state = active_batch_txns[txn_id]
        else:
            cur = self.conn.execute(
                "SELECT transaction_id, status, latest_version FROM transactions WHERE transaction_id = ?;",
                (txn_id,),
            )
            row = cur.fetchone()
            if row:
                current_state = {
                    "transaction_id": row["transaction_id"],
                    "status": row["status"],
                    "latest_version": row["latest_version"],
                }

        # 4. State & sequence validation per event_type
        if ev_type == EventType.CREATE.value:
            if ev_ver != 1:
                return ValidationResult.fail(
                    row_number=row_number,
                    code=RejectionCode.VERSION_CONFLICT,
                    reason=f"CREATE event must have version 1, got {ev_ver}.",
                    raw_payload=raw_payload,
                    event_id=event_id,
                )
            if current_state is not None:
                return ValidationResult.fail(
                    row_number=row_number,
                    code=RejectionCode.INVALID_TRANSACTION_STATE,
                    reason=f"Transaction '{txn_id}' already exists (status: {current_state['status']}). Duplicate creation not allowed.",
                    raw_payload=raw_payload,
                    event_id=event_id,
                )

        elif ev_type == EventType.UPDATE.value:
            if current_state is None:
                return ValidationResult.fail(
                    row_number=row_number,
                    code=RejectionCode.INVALID_TRANSACTION_STATE,
                    reason=f"Cannot UPDATE non-existent transaction '{txn_id}'.",
                    raw_payload=raw_payload,
                    event_id=event_id,
                )
            if current_state["status"] == TransactionStatus.REVERSED.value:
                return ValidationResult.fail(
                    row_number=row_number,
                    code=RejectionCode.INVALID_TRANSACTION_STATE,
                    reason=f"Cannot UPDATE transaction '{txn_id}' because it has already been REVERSED.",
                    raw_payload=raw_payload,
                    event_id=event_id,
                )
            if ev_ver <= current_state["latest_version"]:
                return ValidationResult.fail(
                    row_number=row_number,
                    code=RejectionCode.VERSION_CONFLICT,
                    reason=f"UPDATE version {ev_ver} must be greater than current version {current_state['latest_version']}.",
                    raw_payload=raw_payload,
                    event_id=event_id,
                )

        elif ev_type == EventType.REVERSE.value:
            if current_state is None:
                return ValidationResult.fail(
                    row_number=row_number,
                    code=RejectionCode.INVALID_TRANSACTION_STATE,
                    reason=f"Cannot REVERSE non-existent transaction '{txn_id}'.",
                    raw_payload=raw_payload,
                    event_id=event_id,
                )
            if current_state["status"] == TransactionStatus.REVERSED.value:
                return ValidationResult.fail(
                    row_number=row_number,
                    code=RejectionCode.INVALID_TRANSACTION_STATE,
                    reason=f"Transaction '{txn_id}' is already REVERSED. Repeated reversal prohibited.",
                    raw_payload=raw_payload,
                    event_id=event_id,
                )
            if ev_ver <= current_state["latest_version"]:
                return ValidationResult.fail(
                    row_number=row_number,
                    code=RejectionCode.VERSION_CONFLICT,
                    reason=f"REVERSE version {ev_ver} must be greater than current version {current_state['latest_version']}.",
                    raw_payload=raw_payload,
                    event_id=event_id,
                )

        return ValidationResult.success(record)
