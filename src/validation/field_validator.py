"""
Field-level syntactic and format validation.
"""

from datetime import datetime
from src.config.constants import (
    EventType,
    RejectionCode,
    SUPPORTED_CURRENCIES,
    CANONICAL_COLUMNS,
)
from src.validation.validation_result import ValidationResult


def validate_field_types(row_number: int, row: dict[str, str]) -> ValidationResult:
    """
    Validates field existence, types, numeric formats, and timestamp formats.
    Returns ValidationResult indicating success or failure with appropriate RejectionCode.
    """
    event_id = row.get("event_id", "").strip()

    # 1. Check all canonical columns are present and non-empty
    for col in CANONICAL_COLUMNS:
        val = row.get(col, "")
        if val is None or str(val).strip() == "":
            return ValidationResult.fail(
                row_number=row_number,
                code=RejectionCode.MISSING_REQUIRED_FIELD,
                reason=f"Field '{col}' is required and cannot be empty.",
                raw_payload=row,
                event_id=event_id or None,
            )

    # 2. Event Type Validation
    event_type = row["event_type"].strip()
    if event_type not in {e.value for e in EventType}:
        return ValidationResult.fail(
            row_number=row_number,
            code=RejectionCode.INVALID_EVENT_TYPE,
            reason=f"Invalid event_type '{event_type}'. Must be CREATE, UPDATE, or REVERSE.",
            raw_payload=row,
            event_id=event_id,
        )

    # 3. Event Version Validation
    ver_str = str(row["event_version"]).strip()
    try:
        event_version = int(ver_str)
        if event_version < 1:
            return ValidationResult.fail(
                row_number=row_number,
                code=RejectionCode.VERSION_CONFLICT,
                reason=f"event_version must be >= 1, got {event_version}",
                raw_payload=row,
                event_id=event_id,
            )
    except ValueError:
        return ValidationResult.fail(
            row_number=row_number,
            code=RejectionCode.VERSION_CONFLICT,
            reason=f"event_version must be an integer, got '{ver_str}'",
            raw_payload=row,
            event_id=event_id,
        )

    # 4. Amount Minor Validation
    amt_str = str(row["amount_minor"]).strip()
    try:
        amount_minor = int(amt_str)
        if amount_minor < 0:
            return ValidationResult.fail(
                row_number=row_number,
                code=RejectionCode.INVALID_AMOUNT,
                reason=f"amount_minor cannot be negative, got {amount_minor}",
                raw_payload=row,
                event_id=event_id,
            )
    except ValueError:
        return ValidationResult.fail(
            row_number=row_number,
            code=RejectionCode.INVALID_AMOUNT,
            reason=f"amount_minor must be an integer (in minor units), got '{amt_str}'",
            raw_payload=row,
            event_id=event_id,
        )

    # 5. Timestamp validation (ISO-8601)
    ts_str = row["event_timestamp"].strip()
    try:
        # Standard ISO-8601 parsing
        # Replace trailing 'Z' with +00:00 for Python fromisoformat
        clean_ts = ts_str.replace("Z", "+00:00")
        datetime.fromisoformat(clean_ts)
    except (ValueError, Exception):
        return ValidationResult.fail(
            row_number=row_number,
            code=RejectionCode.INVALID_TIMESTAMP,
            reason=f"Invalid event_timestamp format '{ts_str}'. Expected ISO-8601.",
            raw_payload=row,
            event_id=event_id,
        )

    # 6. Business date validation (YYYY-MM-DD)
    biz_str = row["business_date"].strip()
    try:
        datetime.strptime(biz_str, "%Y-%m-%d")
    except ValueError:
        return ValidationResult.fail(
            row_number=row_number,
            code=RejectionCode.INVALID_TIMESTAMP,
            reason=f"Invalid business_date format '{biz_str}'. Expected YYYY-MM-DD.",
            raw_payload=row,
            event_id=event_id,
        )

    # 7. Currency validation
    curr = row["currency"].strip().upper()
    if curr not in SUPPORTED_CURRENCIES:
        return ValidationResult.fail(
            row_number=row_number,
            code=RejectionCode.MISSING_REQUIRED_FIELD,
            reason=f"Unsupported currency '{curr}'. Supported: {sorted(list(SUPPORTED_CURRENCIES))}",
            raw_payload=row,
            event_id=event_id,
        )

    # Cleaned record with converted types
    cleaned = {
        "event_id": event_id,
        "transaction_id": row["transaction_id"].strip(),
        "event_version": event_version,
        "event_type": event_type,
        "event_timestamp": ts_str,
        "business_date": biz_str,
        "product_id": row["product_id"].strip(),
        "customer_id": row["customer_id"].strip(),
        "amount_minor": amount_minor,
        "currency": curr,
    }

    return ValidationResult.success(cleaned)
