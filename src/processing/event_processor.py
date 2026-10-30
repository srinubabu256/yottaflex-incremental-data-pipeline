"""
Core event processor and pipeline orchestration logic.
Applies deduplication, validation, ledger recording, transaction state transitions,
and affected period detection.
Highly optimized with primary-key batch pre-fetching and monotonic version evaluation.
"""

import sqlite3
import json
import uuid
from datetime import datetime, timezone
from dataclasses import dataclass
from typing import Optional

from src.config.constants import EventType, TransactionStatus, RejectionCode
from src.config.logging_config import get_logger
from src.ingestion.fingerprint import compute_payload_hash
from src.validation.field_validator import validate_field_types
from src.validation.business_validator import BusinessValidator
from src.processing.affected_periods import AffectedPeriodsTracker
from src.processing.transaction_state import (
    apply_create_state,
    apply_update_state,
    apply_reverse_state,
)

logger = get_logger(__name__)


@dataclass
class BatchProcessingStats:
    """Statistics captured during batch processing."""
    input_count: int = 0
    accepted_count: int = 0
    rejected_count: int = 0
    inserted_count: int = 0
    duplicate_count: int = 0
    updated_count: int = 0
    reversed_count: int = 0
    error_count: int = 0


class EventProcessor:
    """Processes incoming batches of transaction events within an active DB transaction."""

    def __init__(self, conn: sqlite3.Connection, run_id: str, source_file: str):
        self.conn = conn
        self.run_id = run_id
        self.source_file = source_file
        self.business_validator = BusinessValidator(conn)
        self.affected_tracker = AffectedPeriodsTracker()
        self.stats = BatchProcessingStats()
        # In-memory tracking within the current batch to handle multiple events for same txn
        self.intra_batch_txns: dict[str, dict] = {}
        # Pre-fetched ledger entries for high-throughput batch deduplication
        self.existing_events_by_id: dict[str, dict] = {}

    def _prefetch_batch_context(self, batch_rows: list[tuple[int, dict[str, str]]]) -> None:
        """Pre-fetches existing transactions and ledger events for the batch via primary keys."""
        distinct_txns = list({r[1].get("transaction_id", "").strip() for r in batch_rows if r[1].get("transaction_id")})
        distinct_events = list({r[1].get("event_id", "").strip() for r in batch_rows if r[1].get("event_id")})

        # 1. Pre-fetch existing transactions (Primary Key lookup)
        for i in range(0, len(distinct_txns), 500):
            chunk = distinct_txns[i : i + 500]
            placeholders = ",".join("?" for _ in chunk)
            cur = self.conn.execute(
                f"""
                SELECT transaction_id, product_id, customer_id, business_date,
                       amount_minor, currency, status, latest_version, created_at, updated_at
                FROM transactions
                WHERE transaction_id IN ({placeholders});
                """,
                chunk,
            )
            for row in cur.fetchall():
                self.intra_batch_txns[row["transaction_id"]] = dict(row)

        # 2. Pre-fetch existing source_events by event_id (Primary Key lookup)
        for i in range(0, len(distinct_events), 500):
            chunk = distinct_events[i : i + 500]
            placeholders = ",".join("?" for _ in chunk)
            cur = self.conn.execute(
                f"""
                SELECT event_id, payload_hash, transaction_id, event_version
                FROM source_events
                WHERE event_id IN ({placeholders});
                """,
                chunk,
            )
            for row in cur.fetchall():
                self.existing_events_by_id[row["event_id"]] = dict(row)

    def process_batch(
        self, batch_rows: list[tuple[int, dict[str, str]]]
    ) -> tuple[BatchProcessingStats, AffectedPeriodsTracker]:
        """Processes a single batch of (source_row_number, row_dict) entries."""
        now_iso = datetime.now(timezone.utc).isoformat()

        # Batch pre-fetch
        self._prefetch_batch_context(batch_rows)

        for row_num, raw_row in batch_rows:
            self.stats.input_count += 1

            # 1. Field validation
            field_result = validate_field_types(row_num, raw_row)
            if not field_result.is_valid:
                self._record_rejection(field_result.failure, now_iso)
                self.stats.rejected_count += 1
                continue

            record = field_result.cleaned_record
            event_id = record["event_id"]
            txn_id = record["transaction_id"]
            event_version = record["event_version"]
            event_type = record["event_type"]
            payload_hash = compute_payload_hash(record)

            # 2. Check Idempotency / Duplicate in historical ledger
            is_dup = False
            is_exact = False
            explanation = ""

            existing_by_id = self.existing_events_by_id.get(event_id)
            if existing_by_id:
                is_dup = True
                if existing_by_id["payload_hash"] == payload_hash:
                    is_exact = True
                    explanation = "Exact duplicate event_id with identical payload."
                else:
                    is_exact = False
                    explanation = "Conflicting payload with identical event_id."
            else:
                # If event_id is new, check if existing transaction already recorded this exact version
                current_state = self.intra_batch_txns.get(txn_id)
                if current_state and event_version <= current_state["latest_version"]:
                    # Check if exact transaction version exists in ledger
                    cur = self.conn.execute(
                        "SELECT event_id, payload_hash FROM source_events WHERE transaction_id = ? AND event_version = ?;",
                        (txn_id, event_version),
                    )
                    existing_ver = cur.fetchone()
                    if existing_ver:
                        is_dup = True
                        if existing_ver["payload_hash"] == payload_hash:
                            is_exact = True
                            explanation = f"Exact duplicate for transaction {txn_id} version {event_version}."
                        else:
                            is_exact = False
                            explanation = f"Conflicting payload for transaction {txn_id} version {event_version}."

            if is_dup:
                if is_exact:
                    # Idempotent re-execution: exact duplicate event previously accepted
                    logger.debug(f"Row {row_num}: Exact duplicate detected for event {event_id}. Skipping.")
                    self.stats.duplicate_count += 1
                    self.stats.accepted_count += 1
                    continue
                else:
                    # Conflicting payload with identical event_id or txn_id + version
                    self._quarantine_record(
                        row_num,
                        event_id,
                        raw_row,
                        RejectionCode.DUPLICATE_EVENT,
                        explanation,
                        now_iso,
                    )
                    self.stats.rejected_count += 1
                    continue

            # 3. Business rule validation
            biz_result = self.business_validator.validate_business_rules(
                row_num, record, self.intra_batch_txns
            )
            if not biz_result.is_valid:
                self._record_rejection(biz_result.failure, now_iso)
                self.stats.rejected_count += 1
                continue

            # 4. Fetch current transaction state
            current_state = self.intra_batch_txns.get(txn_id)

            # Check for late lower version arrival
            if current_state is not None and event_version <= current_state["latest_version"]:
                # Lower version arriving late: out-of-order events must never overwrite newer transaction state
                self._quarantine_record(
                    row_num,
                    event_id,
                    raw_row,
                    RejectionCode.VERSION_CONFLICT,
                    f"Out-of-order event version {event_version} arrived after current version {current_state['latest_version']}.",
                    now_iso,
                )
                self.stats.rejected_count += 1
                continue

            # 5. Insert into immutable ledger (source_events)
            self._insert_source_event(record, row_num, payload_hash, now_iso)

            # Update cached ledger entries
            self.existing_events_by_id[event_id] = {
                "event_id": event_id,
                "payload_hash": payload_hash,
                "transaction_id": txn_id,
                "event_version": event_version,
            }

            # 6. Apply state transition & track affected periods
            if event_type == EventType.CREATE.value:
                apply_create_state(
                    self.conn,
                    txn_id,
                    record["product_id"],
                    record["customer_id"],
                    record["business_date"],
                    record["amount_minor"],
                    record["currency"],
                    event_version,
                    now_iso,
                )
                self.affected_tracker.record_create(
                    record["business_date"],
                    record["product_id"],
                    record["customer_id"],
                )
                self.intra_batch_txns[txn_id] = {
                    "transaction_id": txn_id,
                    "product_id": record["product_id"],
                    "customer_id": record["customer_id"],
                    "business_date": record["business_date"],
                    "amount_minor": record["amount_minor"],
                    "currency": record["currency"],
                    "status": TransactionStatus.ACTIVE.value,
                    "latest_version": event_version,
                }
                self.stats.inserted_count += 1
                self.stats.accepted_count += 1

            elif event_type == EventType.UPDATE.value:
                old_date = current_state["business_date"]
                old_prod = current_state["product_id"]
                old_cust = current_state["customer_id"]

                apply_update_state(
                    self.conn,
                    txn_id,
                    record["product_id"],
                    record["customer_id"],
                    record["business_date"],
                    record["amount_minor"],
                    record["currency"],
                    event_version,
                    now_iso,
                )
                self.affected_tracker.record_update(
                    old_date,
                    old_prod,
                    old_cust,
                    record["business_date"],
                    record["product_id"],
                    record["customer_id"],
                )
                self.intra_batch_txns[txn_id] = {
                    "transaction_id": txn_id,
                    "product_id": record["product_id"],
                    "customer_id": record["customer_id"],
                    "business_date": record["business_date"],
                    "amount_minor": record["amount_minor"],
                    "currency": record["currency"],
                    "status": TransactionStatus.ACTIVE.value,
                    "latest_version": event_version,
                }
                self.stats.updated_count += 1
                self.stats.accepted_count += 1

            elif event_type == EventType.REVERSE.value:
                apply_reverse_state(self.conn, txn_id, event_version, now_iso)
                self.affected_tracker.record_reversal(
                    current_state["business_date"],
                    current_state["product_id"],
                    current_state["customer_id"],
                )
                self.intra_batch_txns[txn_id] = {
                    "transaction_id": txn_id,
                    "product_id": current_state["product_id"],
                    "customer_id": current_state["customer_id"],
                    "business_date": current_state["business_date"],
                    "amount_minor": current_state["amount_minor"],
                    "currency": current_state["currency"],
                    "status": TransactionStatus.REVERSED.value,
                    "latest_version": event_version,
                }
                self.stats.reversed_count += 1
                self.stats.accepted_count += 1

        return self.stats, self.affected_tracker

    def _insert_source_event(
        self, record: dict, row_num: int, payload_hash: str, received_at: str
    ) -> None:
        """Inserts record into immutable historical source_events ledger."""
        self.conn.execute(
            """
            INSERT INTO source_events (
                event_id, transaction_id, event_version, event_type,
                event_timestamp, business_date, product_id, customer_id,
                amount_minor, currency, source_file, source_row_number,
                run_id, payload_hash, received_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
            """,
            (
                record["event_id"],
                record["transaction_id"],
                record["event_version"],
                record["event_type"],
                record["event_timestamp"],
                record["business_date"],
                record["product_id"],
                record["customer_id"],
                record["amount_minor"],
                record["currency"],
                self.source_file,
                row_num,
                self.run_id,
                payload_hash,
                received_at,
            ),
        )

    def _record_rejection(self, failure, received_at: str) -> None:
        """Inserts a validation failure into rejected_records."""
        self._quarantine_record(
            failure.source_row_number,
            failure.event_id,
            failure.raw_payload,
            failure.rejection_code,
            failure.rejection_reason,
            received_at,
        )

    def _quarantine_record(
        self,
        row_num: int,
        event_id: Optional[str],
        raw_payload: str | dict,
        code: RejectionCode,
        reason: str,
        received_at: str,
    ) -> None:
        """Records a quarantined record into the database."""
        reject_id = f"REJ-{uuid.uuid4().hex[:12]}"
        payload_str = raw_payload if isinstance(raw_payload, str) else json.dumps(raw_payload)
        code_str = code.value if hasattr(code, "value") else str(code)

        self.conn.execute(
            """
            INSERT INTO rejected_records (
                reject_id, run_id, source_file, source_row_number,
                event_id, raw_payload, rejection_code, rejection_reason, rejected_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);
            """,
            (
                reject_id,
                self.run_id,
                self.source_file,
                row_num,
                event_id,
                payload_str,
                code_str,
                reason,
                received_at,
            ),
        )
