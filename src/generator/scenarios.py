"""
Curated test scenario generators for verification and sample suites.
Generates distinct files for valid, updates, reversals, late events, and invalid events.
"""

from pathlib import Path
from src.generator.event_generator import SyntheticEventGenerator
from src.config.constants import EventType, DEFAULT_CURRENCY, CANONICAL_COLUMNS
import csv


def generate_all_scenarios(base_sample_dir: Path, seed: int = 42) -> dict[str, Path]:
    """Generates all standard sample scenario files."""
    gen = SyntheticEventGenerator(seed=seed)
    results = {}

    # 1. Valid baseline events
    valid_dir = base_sample_dir / "valid"
    valid_dir.mkdir(parents=True, exist_ok=True)
    valid_file = valid_dir / "events.csv"
    valid_events = gen.generate_events(total_events=50, update_ratio=0.0, reverse_ratio=0.0, late_ratio=0.0)
    gen.write_events_to_csv(valid_file, valid_events)
    results["valid"] = valid_file

    # 2. Updates scenario (takes transactions created in valid and updates them)
    updates_dir = base_sample_dir / "updates"
    updates_dir.mkdir(parents=True, exist_ok=True)
    updates_file = updates_dir / "events.csv"
    update_events = []
    for i, base_ev in enumerate(valid_events[:20], 1):
        update_events.append({
            "event_id": f"EVT-UPD-{i:04d}",
            "transaction_id": base_ev["transaction_id"],
            "event_version": "2",
            "event_type": EventType.UPDATE.value,
            "event_timestamp": "2026-10-26T14:30:00Z",
            "business_date": base_ev["business_date"],
            "product_id": base_ev["product_id"],
            "customer_id": base_ev["customer_id"],
            "amount_minor": str(int(base_ev["amount_minor"]) + 5000),  # Increase amount
            "currency": base_ev["currency"],
        })
    gen.write_events_to_csv(updates_file, update_events)
    results["updates"] = updates_file

    # 3. Reversals scenario (reverses transactions from valid)
    reversals_dir = base_sample_dir / "reversals"
    reversals_dir.mkdir(parents=True, exist_ok=True)
    reversals_file = reversals_dir / "events.csv"
    reverse_events = []
    for i, base_ev in enumerate(valid_events[20:30], 1):
        reverse_events.append({
            "event_id": f"EVT-REV-{i:04d}",
            "transaction_id": base_ev["transaction_id"],
            "event_version": "2",
            "event_type": EventType.REVERSE.value,
            "event_timestamp": "2026-10-27T09:00:00Z",
            "business_date": base_ev["business_date"],
            "product_id": base_ev["product_id"],
            "customer_id": base_ev["customer_id"],
            "amount_minor": base_ev["amount_minor"],
            "currency": base_ev["currency"],
        })
    gen.write_events_to_csv(reversals_file, reverse_events)
    results["reversals"] = reversals_file

    # 4. Late events scenario
    late_dir = base_sample_dir / "late_events"
    late_dir.mkdir(parents=True, exist_ok=True)
    late_file = late_dir / "events.csv"
    late_events = []
    for i in range(1, 15):
        late_events.append({
            "event_id": f"EVT-LATE-{i:04d}",
            "transaction_id": f"TXN-LATE-{i:04d}",
            "event_version": "1",
            "event_type": EventType.CREATE.value,
            "event_timestamp": "2026-10-28T16:00:00Z",
            "business_date": "2026-10-10",  # 18 days late
            "product_id": gen.products[i % len(gen.products)],
            "customer_id": gen.customers[i % len(gen.customers)],
            "amount_minor": "15000",
            "currency": DEFAULT_CURRENCY,
        })
    gen.write_events_to_csv(late_file, late_events)
    results["late_events"] = late_file

    # 5. Invalid events scenario (corrupt data for quarantine testing)
    invalid_dir = base_sample_dir / "invalid_events"
    invalid_dir.mkdir(parents=True, exist_ok=True)
    invalid_file = invalid_dir / "events.csv"
    invalid_events = [
        # Missing required field (product_id empty)
        {
            "event_id": "EVT-INV-0001",
            "transaction_id": "TXN-INV-0001",
            "event_version": "1",
            "event_type": EventType.CREATE.value,
            "event_timestamp": "2026-10-25T10:00:00Z",
            "business_date": "2026-10-25",
            "product_id": "",
            "customer_id": gen.customers[0],
            "amount_minor": "25000",
            "currency": DEFAULT_CURRENCY,
        },
        # Negative amount
        {
            "event_id": "EVT-INV-0002",
            "transaction_id": "TXN-INV-0002",
            "event_version": "1",
            "event_type": EventType.CREATE.value,
            "event_timestamp": "2026-10-25T10:00:00Z",
            "business_date": "2026-10-25",
            "product_id": gen.products[0],
            "customer_id": gen.customers[0],
            "amount_minor": "-5000",
            "currency": DEFAULT_CURRENCY,
        },
        # Unknown product
        {
            "event_id": "EVT-INV-0003",
            "transaction_id": "TXN-INV-0003",
            "event_version": "1",
            "event_type": EventType.CREATE.value,
            "event_timestamp": "2026-10-25T10:00:00Z",
            "business_date": "2026-10-25",
            "product_id": "PRD-UNKNOWN-9999",
            "customer_id": gen.customers[0],
            "amount_minor": "12000",
            "currency": DEFAULT_CURRENCY,
        },
        # Unknown customer
        {
            "event_id": "EVT-INV-0004",
            "transaction_id": "TXN-INV-0004",
            "event_version": "1",
            "event_type": EventType.CREATE.value,
            "event_timestamp": "2026-10-25T10:00:00Z",
            "business_date": "2026-10-25",
            "product_id": gen.products[0],
            "customer_id": "CUST-UNKNOWN-9999",
            "amount_minor": "12000",
            "currency": DEFAULT_CURRENCY,
        },
        # Invalid event type
        {
            "event_id": "EVT-INV-0005",
            "transaction_id": "TXN-INV-0005",
            "event_version": "1",
            "event_type": "DESTROY",
            "event_timestamp": "2026-10-25T10:00:00Z",
            "business_date": "2026-10-25",
            "product_id": gen.products[0],
            "customer_id": gen.customers[0],
            "amount_minor": "12000",
            "currency": DEFAULT_CURRENCY,
        },
    ]
    gen.write_events_to_csv(invalid_file, invalid_events)
    results["invalid_events"] = invalid_file

    return results
