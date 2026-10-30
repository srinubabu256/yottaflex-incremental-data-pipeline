-- ============================================================================
-- YottaFlex Incremental Data Pipeline - Relational Database Schema
-- Target: SQLite 3.35+ (compatible with PostgreSQL with minimal modification)
-- Foreign Key Enforcement: PRAGMA foreign_keys = ON;
-- Monetary Values: Stored as 64-bit integers in minor units (e.g., INR paise)
-- ============================================================================

-- 1. Reference: Products Table
CREATE TABLE IF NOT EXISTS products (
    product_id TEXT PRIMARY KEY,
    product_name TEXT NOT NULL,
    category TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT
);

-- 2. Reference: Customers Table
CREATE TABLE IF NOT EXISTS customers (
    customer_id TEXT PRIMARY KEY,
    customer_name TEXT NOT NULL,
    email TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT
);

-- 3. Operational: Pipeline Runs Table
CREATE TABLE IF NOT EXISTS pipeline_runs (
    run_id TEXT PRIMARY KEY,
    source_file TEXT NOT NULL,
    file_checksum TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('RUNNING', 'SUCCESS', 'PARTIAL', 'FAILED')),
    started_at TEXT NOT NULL,
    completed_at TEXT,
    input_count INTEGER NOT NULL DEFAULT 0,
    accepted_count INTEGER NOT NULL DEFAULT 0,
    rejected_count INTEGER NOT NULL DEFAULT 0,
    inserted_count INTEGER NOT NULL DEFAULT 0,
    duplicate_count INTEGER NOT NULL DEFAULT 0,
    updated_count INTEGER NOT NULL DEFAULT 0,
    reversed_count INTEGER NOT NULL DEFAULT 0,
    error_count INTEGER NOT NULL DEFAULT 0,
    affected_period_count INTEGER NOT NULL DEFAULT 0,
    duration_seconds REAL NOT NULL DEFAULT 0.0,
    failure_reason TEXT
);

-- 4. Ingestion: Source Events Table (Immutable Historical Event Ledger)
CREATE TABLE IF NOT EXISTS source_events (
    event_id TEXT PRIMARY KEY,
    transaction_id TEXT NOT NULL,
    event_version INTEGER NOT NULL CHECK (event_version >= 1),
    event_type TEXT NOT NULL CHECK (event_type IN ('CREATE', 'UPDATE', 'REVERSE')),
    event_timestamp TEXT NOT NULL,
    business_date TEXT NOT NULL,
    product_id TEXT NOT NULL,
    customer_id TEXT NOT NULL,
    amount_minor INTEGER NOT NULL,
    currency TEXT NOT NULL,
    source_file TEXT NOT NULL,
    source_row_number INTEGER NOT NULL,
    run_id TEXT NOT NULL,
    payload_hash TEXT NOT NULL,
    received_at TEXT NOT NULL,
    CONSTRAINT uq_source_events_txn_version UNIQUE (transaction_id, event_version),
    CONSTRAINT fk_source_events_product FOREIGN KEY (product_id) REFERENCES products (product_id),
    CONSTRAINT fk_source_events_customer FOREIGN KEY (customer_id) REFERENCES customers (customer_id),
    CONSTRAINT fk_source_events_run FOREIGN KEY (run_id) REFERENCES pipeline_runs (run_id)
);

-- 5. Authoritative State: Transactions Table (Latest Current State)
CREATE TABLE IF NOT EXISTS transactions (
    transaction_id TEXT PRIMARY KEY,
    product_id TEXT NOT NULL,
    customer_id TEXT NOT NULL,
    business_date TEXT NOT NULL,
    amount_minor INTEGER NOT NULL,
    currency TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('ACTIVE', 'REVERSED')),
    latest_version INTEGER NOT NULL CHECK (latest_version >= 1),
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    CONSTRAINT fk_transactions_product FOREIGN KEY (product_id) REFERENCES products (product_id),
    CONSTRAINT fk_transactions_customer FOREIGN KEY (customer_id) REFERENCES customers (customer_id)
);

-- 6. Quarantine / Audit: Rejected Records Table
CREATE TABLE IF NOT EXISTS rejected_records (
    reject_id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL,
    source_file TEXT NOT NULL,
    source_row_number INTEGER NOT NULL,
    event_id TEXT,
    raw_payload TEXT NOT NULL,
    rejection_code TEXT NOT NULL,
    rejection_reason TEXT NOT NULL,
    rejected_at TEXT NOT NULL,
    CONSTRAINT fk_rejected_records_run FOREIGN KEY (run_id) REFERENCES pipeline_runs (run_id)
);

-- 7. Analytics: Daily Product Metrics
CREATE TABLE IF NOT EXISTS daily_product_metrics (
    business_date TEXT NOT NULL,
    product_id TEXT NOT NULL,
    transaction_count INTEGER NOT NULL,
    total_revenue_minor INTEGER NOT NULL,
    average_amount_minor INTEGER NOT NULL,
    customer_count INTEGER NOT NULL,
    last_recomputed_at TEXT NOT NULL,
    PRIMARY KEY (business_date, product_id),
    CONSTRAINT fk_daily_product_product FOREIGN KEY (product_id) REFERENCES products (product_id)
);

-- 8. Analytics: Daily Customer Metrics
CREATE TABLE IF NOT EXISTS daily_customer_metrics (
    business_date TEXT NOT NULL,
    customer_id TEXT NOT NULL,
    transaction_count INTEGER NOT NULL,
    total_revenue_minor INTEGER NOT NULL,
    average_amount_minor INTEGER NOT NULL,
    product_count INTEGER NOT NULL,
    last_recomputed_at TEXT NOT NULL,
    PRIMARY KEY (business_date, customer_id),
    CONSTRAINT fk_daily_customer_customer FOREIGN KEY (customer_id) REFERENCES customers (customer_id)
);

-- 9. Idempotency: Processed Files Table
CREATE TABLE IF NOT EXISTS processed_files (
    file_id TEXT PRIMARY KEY,
    source_file TEXT NOT NULL,
    file_checksum TEXT UNIQUE NOT NULL,
    run_id TEXT NOT NULL,
    processing_status TEXT NOT NULL,
    processed_at TEXT NOT NULL,
    CONSTRAINT fk_processed_files_run FOREIGN KEY (run_id) REFERENCES pipeline_runs (run_id)
);

-- ============================================================================
-- Performance Indexes
-- ============================================================================
CREATE INDEX IF NOT EXISTS idx_source_events_txn_id ON source_events (transaction_id);
CREATE INDEX IF NOT EXISTS idx_source_events_txn_ver ON source_events (transaction_id, event_version);
CREATE INDEX IF NOT EXISTS idx_source_events_biz_date ON source_events (business_date);
CREATE INDEX IF NOT EXISTS idx_source_events_run_id ON source_events (run_id);
CREATE INDEX IF NOT EXISTS idx_source_events_hash ON source_events (payload_hash);

CREATE INDEX IF NOT EXISTS idx_transactions_biz_prod ON transactions (business_date, product_id);
CREATE INDEX IF NOT EXISTS idx_transactions_biz_cust ON transactions (business_date, customer_id);
CREATE INDEX IF NOT EXISTS idx_transactions_status ON transactions (status);

CREATE INDEX IF NOT EXISTS idx_rejected_records_run_id ON rejected_records (run_id);
CREATE INDEX IF NOT EXISTS idx_rejected_records_code ON rejected_records (rejection_code);

CREATE INDEX IF NOT EXISTS idx_daily_product_date ON daily_product_metrics (business_date);
CREATE INDEX IF NOT EXISTS idx_daily_customer_date ON daily_customer_metrics (business_date);

CREATE INDEX IF NOT EXISTS idx_processed_files_checksum ON processed_files (file_checksum);
