"""
Automated tests for field-level and business-level validation layers.
"""

from src.validation.field_validator import validate_field_types
from src.validation.business_validator import BusinessValidator
from src.config.constants import RejectionCode
from src.database.connection import DatabaseConnection


def test_missing_required_field():
    """Verifies that an empty required field returns MISSING_REQUIRED_FIELD."""
    record = {
        "event_id": "EVT-1",
        "transaction_id": "TXN-1",
        "event_version": "1",
        "event_type": "CREATE",
        "event_timestamp": "2026-10-25T10:00:00Z",
        "business_date": "2026-10-25",
        "product_id": "",  # Missing
        "customer_id": "CUST-0001",
        "amount_minor": "1000",
        "currency": "INR",
    }
    res = validate_field_types(2, record)
    assert res.is_valid is False
    assert res.failure.rejection_code == RejectionCode.MISSING_REQUIRED_FIELD


def test_invalid_negative_amount():
    """Verifies that negative amounts return INVALID_AMOUNT."""
    record = {
        "event_id": "EVT-1",
        "transaction_id": "TXN-1",
        "event_version": "1",
        "event_type": "CREATE",
        "event_timestamp": "2026-10-25T10:00:00Z",
        "business_date": "2026-10-25",
        "product_id": "PRD-0001",
        "customer_id": "CUST-0001",
        "amount_minor": "-500",
        "currency": "INR",
    }
    res = validate_field_types(2, record)
    assert res.is_valid is False
    assert res.failure.rejection_code == RejectionCode.INVALID_AMOUNT


def test_invalid_timestamp_format():
    """Verifies that malformed ISO-8601 timestamps return INVALID_TIMESTAMP."""
    record = {
        "event_id": "EVT-1",
        "transaction_id": "TXN-1",
        "event_version": "1",
        "event_type": "CREATE",
        "event_timestamp": "25-10-2026 10:00",
        "business_date": "2026-10-25",
        "product_id": "PRD-0001",
        "customer_id": "CUST-0001",
        "amount_minor": "1000",
        "currency": "INR",
    }
    res = validate_field_types(2, record)
    assert res.is_valid is False
    assert res.failure.rejection_code == RejectionCode.INVALID_TIMESTAMP


def test_invalid_event_type():
    """Verifies that unrecognised event types return INVALID_EVENT_TYPE."""
    record = {
        "event_id": "EVT-1",
        "transaction_id": "TXN-1",
        "event_version": "1",
        "event_type": "MODIFY",
        "event_timestamp": "2026-10-25T10:00:00Z",
        "business_date": "2026-10-25",
        "product_id": "PRD-0001",
        "customer_id": "CUST-0001",
        "amount_minor": "1000",
        "currency": "INR",
    }
    res = validate_field_types(2, record)
    assert res.is_valid is False
    assert res.failure.rejection_code == RejectionCode.INVALID_EVENT_TYPE


def test_unknown_product_validation(temp_db: DatabaseConnection):
    """Verifies that non-existent product IDs return UNKNOWN_PRODUCT."""
    with temp_db.connection() as conn:
        validator = BusinessValidator(conn)
        record = {
            "event_id": "EVT-1",
            "transaction_id": "TXN-1",
            "event_version": 1,
            "event_type": "CREATE",
            "event_timestamp": "2026-10-25T10:00:00Z",
            "business_date": "2026-10-25",
            "product_id": "PRD-UNKNOWN-9999",
            "customer_id": "CUST-0001",
            "amount_minor": 1000,
            "currency": "INR",
        }
        res = validator.validate_business_rules(2, record)
        assert res.is_valid is False
        assert res.failure.rejection_code == RejectionCode.UNKNOWN_PRODUCT


def test_unknown_customer_validation(temp_db: DatabaseConnection):
    """Verifies that non-existent customer IDs return UNKNOWN_CUSTOMER."""
    with temp_db.connection() as conn:
        validator = BusinessValidator(conn)
        record = {
            "event_id": "EVT-1",
            "transaction_id": "TXN-1",
            "event_version": 1,
            "event_type": "CREATE",
            "event_timestamp": "2026-10-25T10:00:00Z",
            "business_date": "2026-10-25",
            "product_id": "PRD-0001",
            "customer_id": "CUST-UNKNOWN-9999",
            "amount_minor": 1000,
            "currency": "INR",
        }
        res = validator.validate_business_rules(2, record)
        assert res.is_valid is False
        assert res.failure.rejection_code == RejectionCode.UNKNOWN_CUSTOMER
