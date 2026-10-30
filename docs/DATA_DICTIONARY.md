# YottaFlex Data Dictionary

This document provides a comprehensive technical reference for all 9 relational tables within the YottaFlex Incremental Data Engineering Pipeline database schema.

---

## 1. products

Master catalog of reference product entities available for transactions.

| Column Name | Data Type | Nullable | Primary Key | Foreign Key | Description |
|---|---|---|---|---|---|
| `product_id` | TEXT | No | Yes | None | Unique business identifier for the product (e.g. `PRD-0001`). |
| `product_name` | TEXT | No | No | None | Human-readable product title / name. |
| `category` | TEXT | Yes | No | None | Product category (e.g., Electronics, Apparel, Home & Kitchen). |
| `created_at` | TEXT | No | No | None | ISO-8601 UTC timestamp of record creation. |
| `updated_at` | TEXT | Yes | No | None | ISO-8601 UTC timestamp of last metadata modification. |

---

## 2. customers

Master catalog of synthetic reference customer entities.

| Column Name | Data Type | Nullable | Primary Key | Foreign Key | Description |
|---|---|---|---|---|---|
| `customer_id` | TEXT | No | Yes | None | Unique customer business identifier (e.g. `CUST-0001`). |
| `customer_name` | TEXT | No | No | None | Synthetic full customer name. |
| `email` | TEXT | Yes | No | None | Synthetic contact email address. |
| `created_at` | TEXT | No | No | None | ISO-8601 UTC timestamp of record creation. |
| `updated_at` | TEXT | Yes | No | None | ISO-8601 UTC timestamp of last metadata modification. |

---

## 3. pipeline_runs

Audit ledger tracking every execution lifecycle of the pipeline.

| Column Name | Data Type | Nullable | Primary Key | Foreign Key | Description |
|---|---|---|---|---|---|
| `run_id` | TEXT | No | Yes | None | Unique run identifier (e.g. `RUN-20261030070037-22be17`). |
| `source_file` | TEXT | No | No | None | Absolute or relative path to the processed input CSV file. |
| `file_checksum` | TEXT | No | No | None | SHA-256 cryptographic digest of the ingested file. |
| `status` | TEXT | No | No | None | Execution outcome: `RUNNING`, `SUCCESS`, `PARTIAL`, `FAILED`. |
| `started_at` | TEXT | No | No | None | ISO-8601 UTC timestamp of run initialization. |
| `completed_at` | TEXT | Yes | No | None | ISO-8601 UTC timestamp of run termination. |
| `input_count` | INTEGER | No | No | None | Total raw records streamed from input file. |
| `accepted_count` | INTEGER | No | No | None | Total records accepted and applied or deduplicated. |
| `rejected_count` | INTEGER | No | No | None | Total records quarantined in `rejected_records`. |
| `inserted_count` | INTEGER | No | No | None | Count of newly created transactions. |
| `duplicate_count` | INTEGER | No | No | None | Count of exact duplicate events safely ignored. |
| `updated_count` | INTEGER | No | No | None | Count of applied `UPDATE` events. |
| `reversed_count` | INTEGER | No | No | None | Count of applied `REVERSE` events. |
| `error_count` | INTEGER | No | No | None | Internal system exceptions encountered during run. |
| `affected_period_count` | INTEGER | No | No | None | Count of distinct `(date, entity)` partition groups recomputed. |
| `duration_seconds` | REAL | No | No | None | Total execution duration measured via `time.perf_counter()`. |
| `failure_reason` | TEXT | Yes | No | None | Error stack trace or message in case of `FAILED` status. |

---

## 4. source_events

Immutable append-only ledger recording all accepted historical transaction event snapshots.

| Column Name | Data Type | Nullable | Primary Key | Foreign Key | Description |
|---|---|---|---|---|---|
| `event_id` | TEXT | No | Yes | None | Canonical event identifier (e.g. `EVT-00000001`). |
| `transaction_id` | TEXT | No | No | None | Business identifier of the underlying transaction. |
| `event_version` | INTEGER | No | No | None | Strictly positive monotonic event sequence number ($\ge 1$). |
| `event_type` | TEXT | No | No | None | Event operation: `CREATE`, `UPDATE`, or `REVERSE`. |
| `event_timestamp` | TEXT | No | No | None | ISO-8601 UTC timestamp when the event occurred in source domain. |
| `business_date` | TEXT | No | No | None | Reporting calendar date formatted as `YYYY-MM-DD`. |
| `product_id` | TEXT | No | No | `products.product_id` | Reference to product catalog. |
| `customer_id` | TEXT | No | No | `customers.customer_id` | Reference to customer catalog. |
| `amount_minor` | INTEGER | No | No | None | Non-negative integer value in minor currency units (paise for INR). |
| `currency` | TEXT | No | No | None | ISO-4217 3-letter currency code (e.g. `INR`). |
| `source_file` | TEXT | No | No | None | Input file where this event was received. |
| `source_row_number` | INTEGER | No | No | None | 1-based row number in the source CSV file (line 1 = header). |
| `run_id` | TEXT | No | No | `pipeline_runs.run_id` | The pipeline execution run that processed this event. |
| `payload_hash` | TEXT | No | No | None | SHA-256 digest of normalized canonical event payload. |
| `received_at` | TEXT | No | No | None | ISO-8601 UTC timestamp of ingestion into YottaFlex database. |

*Unique Constraint*: `UNIQUE(transaction_id, event_version)` guarantees monotonic version integrity.

---

## 5. transactions

Authoritative current state table storing the latest active or reversed state of each transaction.

| Column Name | Data Type | Nullable | Primary Key | Foreign Key | Description |
|---|---|---|---|---|---|
| `transaction_id` | TEXT | No | Yes | None | Primary business transaction identifier. |
| `product_id` | TEXT | No | No | `products.product_id` | Current product assignment. |
| `customer_id` | TEXT | No | No | `customers.customer_id` | Current customer assignment. |
| `business_date` | TEXT | No | No | None | Current reporting business date (`YYYY-MM-DD`). |
| `amount_minor` | INTEGER | No | No | None | Current transaction monetary amount in integer minor units. |
| `currency` | TEXT | No | No | None | Currency identifier (`INR`). |
| `status` | TEXT | No | No | None | Current state: `ACTIVE` or `REVERSED`. |
| `latest_version` | INTEGER | No | No | None | Highest event version applied to this transaction. |
| `created_at` | TEXT | No | No | None | ISO-8601 UTC timestamp when transaction was first created. |
| `updated_at` | TEXT | No | No | None | ISO-8601 UTC timestamp when transaction was last modified. |

---

## 6. rejected_records

Quarantine audit table capturing every rejected row, validation error, and payload for full traceability.

| Column Name | Data Type | Nullable | Primary Key | Foreign Key | Description |
|---|---|---|---|---|---|
| `reject_id` | TEXT | No | Yes | None | Unique rejection identifier (e.g. `REJ-aecdf1fcea77`). |
| `run_id` | TEXT | No | No | `pipeline_runs.run_id` | Pipeline run during which record was quarantined. |
| `source_file` | TEXT | No | No | None | Input CSV file path containing the defective row. |
| `source_row_number` | INTEGER | No | No | None | Exact line number in input CSV. |
| `event_id` | TEXT | Yes | No | None | Event ID from row if parseable, or NULL. |
| `raw_payload` | TEXT | No | No | None | Exact JSON string representation of the raw input row. |
| `rejection_code` | TEXT | No | No | None | Standard rejection code (e.g. `UNKNOWN_PRODUCT`). |
| `rejection_reason` | TEXT | No | No | None | Detailed human-readable explanation of rejection cause. |
| `rejected_at` | TEXT | No | No | None | ISO-8601 UTC timestamp when row was quarantined. |

---

## 7. daily_product_metrics

Aggregated reporting table maintaining daily product performance metrics computed exclusively from `ACTIVE` transactions.

| Column Name | Data Type | Nullable | Primary Key | Foreign Key | Description |
|---|---|---|---|---|---|
| `business_date` | TEXT | No | Composite PK | None | Reporting date (`YYYY-MM-DD`). |
| `product_id` | TEXT | No | Composite PK | `products.product_id` | Product entity identifier. |
| `transaction_count` | INTEGER | No | No | None | Total count of active transactions for this partition. |
| `total_revenue_minor` | INTEGER | No | No | None | Total revenue in integer minor units (paise). |
| `average_amount_minor` | INTEGER | No | No | None | Truncated integer average transaction value (`total // count`). |
| `customer_count` | INTEGER | No | No | None | Count of distinct customers purchasing this product on this date. |
| `last_recomputed_at` | TEXT | No | No | None | ISO-8601 UTC timestamp of last incremental recomputation. |

---

## 8. daily_customer_metrics

Aggregated reporting table maintaining daily customer metrics computed exclusively from `ACTIVE` transactions.

| Column Name | Data Type | Nullable | Primary Key | Foreign Key | Description |
|---|---|---|---|---|---|
| `business_date` | TEXT | No | Composite PK | None | Reporting date (`YYYY-MM-DD`). |
| `customer_id` | TEXT | No | Composite PK | `customers.customer_id` | Customer entity identifier. |
| `transaction_count` | INTEGER | No | No | None | Total count of active transactions for this customer on this date. |
| `total_revenue_minor` | INTEGER | No | No | None | Total spend in integer minor units (paise). |
| `average_amount_minor` | INTEGER | No | No | None | Truncated integer average transaction value. |
| `product_count` | INTEGER | No | No | None | Count of distinct products purchased by this customer on this date. |
| `last_recomputed_at` | TEXT | No | No | None | ISO-8601 UTC timestamp of last incremental recomputation. |

---

## 9. processed_files

Idempotency tracking ledger recording files that have been successfully ingested.

| Column Name | Data Type | Nullable | Primary Key | Foreign Key | Description |
|---|---|---|---|---|---|
| `file_id` | TEXT | No | Yes | None | Unique file registration identifier (`FIL-...`). |
| `source_file` | TEXT | No | No | None | Path of processed file. |
| `file_checksum` | TEXT | No | No (Unique) | None | Cryptographic SHA-256 checksum of raw file bytes. |
| `run_id` | TEXT | No | No | `pipeline_runs.run_id` | Pipeline run that processed the file. |
| `processing_status` | TEXT | No | No | None | Processing state (`SUCCESS`, `PARTIAL`). |
| `processed_at` | TEXT | No | No | None | ISO-8601 UTC timestamp when file processing finished. |
