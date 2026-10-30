"""
Data models representing database entities and records.
"""

from dataclasses import dataclass
from typing import Optional


@dataclass
class Product:
    product_id: str
    product_name: str
    category: Optional[str] = None
    created_at: str = ""
    updated_at: Optional[str] = None


@dataclass
class Customer:
    customer_id: str
    customer_name: str
    email: Optional[str] = None
    created_at: str = ""
    updated_at: Optional[str] = None


@dataclass
class PipelineRun:
    run_id: str
    source_file: str
    file_checksum: str
    status: str
    started_at: str
    completed_at: Optional[str] = None
    input_count: int = 0
    accepted_count: int = 0
    rejected_count: int = 0
    inserted_count: int = 0
    duplicate_count: int = 0
    updated_count: int = 0
    reversed_count: int = 0
    error_count: int = 0
    affected_period_count: int = 0
    duration_seconds: float = 0.0
    failure_reason: Optional[str] = None


@dataclass
class SourceEvent:
    event_id: str
    transaction_id: str
    event_version: int
    event_type: str
    event_timestamp: str
    business_date: str
    product_id: str
    customer_id: str
    amount_minor: int
    currency: str
    source_file: str
    source_row_number: int
    run_id: str
    payload_hash: str
    received_at: str


@dataclass
class Transaction:
    transaction_id: str
    product_id: str
    customer_id: str
    business_date: str
    amount_minor: int
    currency: str
    status: str
    latest_version: int
    created_at: str
    updated_at: str


@dataclass
class RejectedRecord:
    reject_id: str
    run_id: str
    source_file: str
    source_row_number: int
    event_id: Optional[str]
    raw_payload: str
    rejection_code: str
    rejection_reason: str
    rejected_at: str


@dataclass
class DailyProductMetric:
    business_date: str
    product_id: str
    transaction_count: int
    total_revenue_minor: int
    average_amount_minor: int
    customer_count: int
    last_recomputed_at: str


@dataclass
class DailyCustomerMetric:
    business_date: str
    customer_id: str
    transaction_count: int
    total_revenue_minor: int
    average_amount_minor: int
    product_count: int
    last_recomputed_at: str


@dataclass
class ProcessedFile:
    file_id: str
    source_file: str
    file_checksum: str
    run_id: str
    processing_status: str
    processed_at: str
