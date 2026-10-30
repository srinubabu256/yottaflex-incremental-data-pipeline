"""
Validation result and failure representations.
"""

import json
from dataclasses import dataclass
from typing import Optional, Any
from src.config.constants import RejectionCode


@dataclass
class ValidationFailure:
    """Represents a single validation error on a row."""
    source_row_number: int
    rejection_code: RejectionCode
    rejection_reason: str
    raw_payload: str
    event_id: Optional[str] = None


@dataclass
class ValidationResult:
    """Represents the outcome of validating a single record."""
    is_valid: bool
    failure: Optional[ValidationFailure] = None
    cleaned_record: Optional[dict[str, Any]] = None

    @classmethod
    def success(cls, cleaned_record: dict[str, Any]) -> "ValidationResult":
        return cls(is_valid=True, cleaned_record=cleaned_record)

    @classmethod
    def fail(
        cls,
        row_number: int,
        code: RejectionCode,
        reason: str,
        raw_payload: dict | str,
        event_id: Optional[str] = None,
    ) -> "ValidationResult":
        raw_str = raw_payload if isinstance(raw_payload, str) else json.dumps(raw_payload)
        failure = ValidationFailure(
            source_row_number=row_number,
            rejection_code=code,
            rejection_reason=reason,
            raw_payload=raw_str,
            event_id=event_id,
        )
        return cls(is_valid=False, failure=failure)
