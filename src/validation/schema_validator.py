"""
CSV Header and Schema structure validator.
"""

from src.config.constants import CANONICAL_COLUMNS, RejectionCode
from src.validation.validation_result import ValidationResult


class SchemaValidationError(Exception):
    """Raised when the CSV schema does not match canonical structure."""
    def __init__(self, code: RejectionCode, reason: str):
        self.code = code
        self.reason = reason
        super().__init__(reason)


def validate_csv_schema(headers: list[str]) -> None:
    """
    Validates CSV headers against canonical column specification.
    Raises SchemaValidationError if required columns are missing or if unexpected columns exist.
    """
    if not headers:
        raise SchemaValidationError(
            RejectionCode.SCHEMA_MISMATCH,
            "CSV file has no headers.",
        )

    header_set = set(headers)
    canonical_set = set(CANONICAL_COLUMNS)

    missing = canonical_set - header_set
    if missing:
        raise SchemaValidationError(
            RejectionCode.SCHEMA_MISMATCH,
            f"Missing required columns in CSV header: {sorted(list(missing))}",
        )

    unexpected = header_set - canonical_set
    if unexpected:
        raise SchemaValidationError(
            RejectionCode.SCHEMA_MISMATCH,
            f"Unexpected columns found in CSV header: {sorted(list(unexpected))}",
        )
