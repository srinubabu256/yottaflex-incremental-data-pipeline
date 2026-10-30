"""
Reproducible synthetic transaction event generator for YottaFlex.
Supports generation of 100 to 100,000+ realistic transaction events.
"""

import csv
import random
from datetime import datetime, timedelta, timezone
from pathlib import Path
from src.config.constants import CANONICAL_COLUMNS, EventType, DEFAULT_CURRENCY
from src.generator.reference_generator import generate_reference_products, generate_reference_customers


class SyntheticEventGenerator:
    """Generates realistic incremental event streams."""

    def __init__(self, seed: int = 42, product_count: int = 50, customer_count: int = 100):
        self.seed = seed
        self.rng = random.Random(seed)
        self.products = [p["product_id"] for p in generate_reference_products(product_count, seed)]
        self.customers = [c["customer_id"] for c in generate_reference_customers(customer_count, seed)]
        self.base_date = datetime(2026, 10, 15, 10, 0, 0, tzinfo=timezone.utc)

    def generate_events(
        self,
        total_events: int = 1000,
        update_ratio: float = 0.15,
        reverse_ratio: float = 0.05,
        late_ratio: float = 0.05,
        invalid_ratio: float = 0.0,
    ) -> list[dict[str, str]]:
        """
        Generates logically consistent transaction events.
        Maintains an active transaction pool so UPDATE and REVERSE events have valid references and versions.
        """
        events: list[dict[str, str]] = []
        active_transactions: dict[str, dict] = {}
        txn_counter = 1

        for i in range(1, total_events + 1):
            event_id = f"EVT-{i:08d}"

            # Check if this should be an invalid event
            if invalid_ratio > 0 and self.rng.random() < invalid_ratio:
                events.append(self._generate_invalid_event(event_id, i))
                continue

            # Determine event type
            roll = self.rng.random()
            if roll < reverse_ratio and active_transactions:
                # REVERSE
                txn_id = self.rng.choice(list(active_transactions.keys()))
                state = active_transactions.pop(txn_id)
                new_ver = state["version"] + 1
                ev_time = state["timestamp"] + timedelta(hours=self.rng.randint(2, 48))
                event = {
                    "event_id": event_id,
                    "transaction_id": txn_id,
                    "event_version": str(new_ver),
                    "event_type": EventType.REVERSE.value,
                    "event_timestamp": ev_time.isoformat(),
                    "business_date": state["business_date"],
                    "product_id": state["product_id"],
                    "customer_id": state["customer_id"],
                    "amount_minor": str(state["amount_minor"]),
                    "currency": state["currency"],
                }
                events.append(event)

            elif roll < (reverse_ratio + update_ratio) and active_transactions:
                # UPDATE
                txn_id = self.rng.choice(list(active_transactions.keys()))
                state = active_transactions[txn_id]
                new_ver = state["version"] + 1
                ev_time = state["timestamp"] + timedelta(hours=self.rng.randint(1, 24))

                # Update may change amount, or occasionally product/customer/date
                new_amount = max(100, state["amount_minor"] + self.rng.choice([-5000, 5000, 10000, -2000]))
                new_prod = state["product_id"] if self.rng.random() > 0.1 else self.rng.choice(self.products)
                new_cust = state["customer_id"] if self.rng.random() > 0.05 else self.rng.choice(self.customers)
                new_date = state["business_date"]
                if self.rng.random() < 0.05:
                    dt = datetime.strptime(state["business_date"], "%Y-%m-%d") + timedelta(days=self.rng.choice([-1, 1]))
                    new_date = dt.strftime("%Y-%m-%d")

                state["version"] = new_ver
                state["amount_minor"] = new_amount
                state["product_id"] = new_prod
                state["customer_id"] = new_cust
                state["business_date"] = new_date
                state["timestamp"] = ev_time

                event = {
                    "event_id": event_id,
                    "transaction_id": txn_id,
                    "event_version": str(new_ver),
                    "event_type": EventType.UPDATE.value,
                    "event_timestamp": ev_time.isoformat(),
                    "business_date": new_date,
                    "product_id": new_prod,
                    "customer_id": new_cust,
                    "amount_minor": str(new_amount),
                    "currency": state["currency"],
                }
                events.append(event)

            else:
                # CREATE
                txn_id = f"TXN-{txn_counter:07d}"
                txn_counter += 1
                day_offset = self.rng.randint(0, 14)
                ev_time = self.base_date + timedelta(days=day_offset, minutes=self.rng.randint(0, 1440))
                biz_date = ev_time.strftime("%Y-%m-%d")

                # Late event scenario: event occurred a few days earlier than current run window
                if self.rng.random() < late_ratio:
                    biz_date = (ev_time - timedelta(days=self.rng.randint(2, 5))).strftime("%Y-%m-%d")

                prod_id = self.rng.choice(self.products)
                cust_id = self.rng.choice(self.customers)
                amount = self.rng.randint(100, 100000) * 100  # Stored in paise (integer)

                active_transactions[txn_id] = {
                    "version": 1,
                    "timestamp": ev_time,
                    "business_date": biz_date,
                    "product_id": prod_id,
                    "customer_id": cust_id,
                    "amount_minor": amount,
                    "currency": DEFAULT_CURRENCY,
                }

                event = {
                    "event_id": event_id,
                    "transaction_id": txn_id,
                    "event_version": "1",
                    "event_type": EventType.CREATE.value,
                    "event_timestamp": ev_time.isoformat(),
                    "business_date": biz_date,
                    "product_id": prod_id,
                    "customer_id": cust_id,
                    "amount_minor": str(amount),
                    "currency": DEFAULT_CURRENCY,
                }
                events.append(event)

        return events

    def _generate_invalid_event(self, event_id: str, row_num: int) -> dict[str, str]:
        """Generates an intentionally defective event to test quarantine."""
        case = row_num % 5
        base = {
            "event_id": event_id,
            "transaction_id": f"TXN-INV-{row_num:05d}",
            "event_version": "1",
            "event_type": EventType.CREATE.value,
            "event_timestamp": "2026-10-25T12:00:00Z",
            "business_date": "2026-10-25",
            "product_id": self.products[0],
            "customer_id": self.customers[0],
            "amount_minor": "50000",
            "currency": DEFAULT_CURRENCY,
        }
        if case == 0:
            base["amount_minor"] = "-1000"  # Negative amount
        elif case == 1:
            base["product_id"] = "PRD-UNKNOWN-9999"  # Unknown product
        elif case == 2:
            base["customer_id"] = "CUST-UNKNOWN-9999"  # Unknown customer
        elif case == 3:
            base["event_timestamp"] = "invalid-timestamp"  # Bad timestamp
        elif case == 4:
            base["event_type"] = "INVALID_TYPE"  # Bad event type
        return base

    def write_events_to_csv(self, file_path: Path, events: list[dict[str, str]]) -> None:
        """Writes events list to a CSV file."""
        file_path.parent.mkdir(parents=True, exist_ok=True)
        with open(file_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=CANONICAL_COLUMNS)
            writer.writeheader()
            writer.writerows(events)
