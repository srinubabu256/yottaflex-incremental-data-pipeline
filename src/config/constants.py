"""
Constants and enumerations for YottaFlex Data Pipeline.
"""

from enum import Enum


class EventType(str, Enum):
    CREATE = "CREATE"
    UPDATE = "UPDATE"
    REVERSE = "REVERSE"


class TransactionStatus(str, Enum):
    ACTIVE = "ACTIVE"
    REVERSED = "REVERSED"


class PipelineRunStatus(str, Enum):
    RUNNING = "RUNNING"
    SUCCESS = "SUCCESS"
    PARTIAL = "PARTIAL"
    FAILED = "FAILED"


class RejectionCode(str, Enum):
    MISSING_REQUIRED_FIELD = "MISSING_REQUIRED_FIELD"
    INVALID_AMOUNT = "INVALID_AMOUNT"
    INVALID_TIMESTAMP = "INVALID_TIMESTAMP"
    UNKNOWN_PRODUCT = "UNKNOWN_PRODUCT"
    UNKNOWN_CUSTOMER = "UNKNOWN_CUSTOMER"
    DUPLICATE_EVENT = "DUPLICATE_EVENT"
    VERSION_CONFLICT = "VERSION_CONFLICT"
    INVALID_EVENT_TYPE = "INVALID_EVENT_TYPE"
    INVALID_TRANSACTION_STATE = "INVALID_TRANSACTION_STATE"
    SCHEMA_MISMATCH = "SCHEMA_MISMATCH"


# Canonical CSV Header specification
CANONICAL_COLUMNS = [
    "event_id",
    "transaction_id",
    "event_version",
    "event_type",
    "event_timestamp",
    "business_date",
    "product_id",
    "customer_id",
    "amount_minor",
    "currency",
]

# Supported Currencies
SUPPORTED_CURRENCIES = {"INR", "USD", "EUR", "GBP"}
DEFAULT_CURRENCY = "INR"
