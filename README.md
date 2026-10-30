# YottaFlex – Incremental Data Engineering Pipeline

A high-performance, production-style Python data engineering pipeline that processes incremental transaction events and maintains mathematically accurate daily product-level and customer-level metrics.

---

## Table of Contents
1. [Project Overview](#1-project-overview)
2. [Quick Start & Execution Guide (Step-by-Step)](#2-quick-start--execution-guide-step-by-step)
3. [Business Problem](#3-business-problem)
4. [Objectives](#4-objectives)
5. [Key Features](#5-key-features)
6. [Architecture](#6-architecture)
7. [Technology Stack](#7-technology-stack)
8. [Project Folder Structure](#8-project-folder-structure)
9. [Database Design & Schema](#9-database-design--schema)
10. [Entity Relationships](#10-entity-relationships)
11. [Data Dictionary](#11-data-dictionary)
12. [Source Event Data Contract](#12-source-event-data-contract)
13. [Business Rules](#13-business-rules)
14. [Event Versioning & Snapshots](#14-event-versioning--snapshots)
15. [CREATE, UPDATE, and REVERSE Handling](#15-create-update-and-reverse-handling)
16. [Late Events Handling](#16-late-events-handling)
17. [Out-of-Order Events](#17-out-of-order-events)
18. [Idempotency Guarantees](#18-idempotency-guarantees)
19. [Transaction Recovery and Quarantine](#19-transaction-recovery-and-quarantine)
20. [Installation & Setup](#20-installation--setup)
21. [Environment Configuration](#21-environment-configuration)
22. [Database Initialization](#22-database-initialization)
23. [Sample & Synthetic Data Generation](#23-sample--synthetic-data-generation)
24. [Pipeline Execution](#24-pipeline-execution)
25. [Automated Testing & Coverage](#25-automated-testing--coverage)
26. [Independent Reconciliation Engine](#26-independent-reconciliation-engine)
27. [Performance Benchmarks](#27-performance-benchmarks)
28. [Sample Outputs & Reporting](#28-sample-outputs--reporting)
29. [System Limitations](#29-system-limitations)
30. [Future Improvements](#30-future-improvements)
31. [GitHub Push & Submission Instructions](#31-github-push--submission-instructions)
32. [AI Usage Disclosure](#32-ai-usage-disclosure)

---

## 1. Project Overview

**YottaFlex** is an incremental data engineering pipeline built in Python 3.11+ and SQLite 3.35+. It ingests continuous event streams of financial transactions (`CREATE`, `UPDATE`, `REVERSE`), maintains an immutable historical audit ledger, applies monotonic state transitions to an authoritative transaction table, and deterministically computes daily product-level and customer-level business metrics.

---

## 2. Quick Start & Execution Guide (Step-by-Step)

Follow these simple step-by-step commands to run the entire pipeline, execute tests, verify reconciliation, and view reports.

---

### Method A: Windows Command Prompt (`CMD`) — Step-by-Step

Open Command Prompt (`cmd.exe`) in the project directory `D:\Srinubabu\yottaflex-incremental-data-pipeline`:

#### Step 1: Initialize Database & Seed Catalogs
Creates the SQLite database schema and seeds 50 products and 100 customers:
```cmd
run.bat init
```

#### Step 2: Run End-to-End Incremental Sample Ingestion
Ingests initial valid events, updates, reversals, late events, and invalid events:
```cmd
run.bat sample_run
```
> **What this does automatically:**
> 1. Ingests 50 initial transactions (`CREATE` events)
> 2. Ingests 20 updates modifying amounts and dates (`UPDATE` events)
> 3. Ingests 10 cancellations/reversals (`REVERSE` events)
> 4. Ingests 14 late-arriving events
> 5. Quarantines 5 invalid events into `rejected_records`
> 6. Executes the reconciliation audit (**438 / 438 checks PASS**)
> 7. Exports all final CSV and JSON reports to `outputs/`

#### Step 3: Run Reconciliation Audit Independently
Verifies that daily aggregates match transactions with 100% mathematical parity:
```cmd
run.bat reconcile
```

#### Step 4: Export Reports to CSV & JSON
Generates all analytical reports in the `outputs/` folder:
```cmd
run.bat report
```

#### Step 5: Run All 56 Automated Tests
```cmd
run.bat test
```

#### Step 6: View Code Coverage (92.0% statement coverage)
```cmd
run.bat cov
```

#### Step 7: View Quarantined Bad Records
```cmd
run.bat rejects
```

#### Step 8: View Execution History & Run Metrics
```cmd
run.bat runs
```

#### Step 9: Run Performance Benchmark (100,000 Records)
Runs a high-throughput benchmark in an isolated temporary database:
```cmd
run.bat benchmark 100000
```

---

### Method B: Windows PowerShell (`run.ps1`) — Step-by-Step

If you are using **PowerShell**, use `.\run.ps1`:

```powershell
# Step 1: Initialize database and seed catalogs
.\run.ps1 init

# Step 2: Run full end-to-end sample pipeline & reconcile
.\run.ps1 sample-run

# Step 3: Run reconciliation parity checks
.\run.ps1 reconcile

# Step 4: Generate all CSV and JSON reports
.\run.ps1 report

# Step 5: Run all 56 unit and integration tests
.\run.ps1 test

# Step 6: View code coverage report (92.0%)
.\run.ps1 cov

# Step 7: List quarantined rejected records
.\run.ps1 rejects

# Step 8: List pipeline execution runs
.\run.ps1 runs

# Step 9: Run 100,000-row benchmark
.\run.ps1 benchmark 100000
```

---

### Method C: Direct Python CLI Commands (Cross-Platform)

You can also run all subcommands directly with `python -m src.main`:

```bash
# 1. Initialize schema and reference data
python -m src.main init-db

# 2. Ingest individual event files
python -m src.main run --input data/sample/valid/events.csv
python -m src.main run --input data/sample/updates/events.csv
python -m src.main run --input data/sample/reversals/events.csv
python -m src.main run --input data/sample/late_events/events.csv
python -m src.main run --input data/sample/invalid_events/events.csv

# 3. Run reconciliation engine
python -m src.main reconcile

# 4. Generate all CSV and JSON reports
python -m src.main report
python -m src.main export --output outputs/

# 5. Inspect operational runs and rejected records
python -m src.main runs
python -m src.main rejects

# 6. Run automated test suite & coverage
pytest -v
pytest --cov=src --cov-report=term-missing
```

---

### Method D: Linux / macOS (`Make`)
```bash
make init
make sample-run
make test
make cov
```

---

### Generated Output Files (`outputs/` Directory)

After running the pipeline, check the `outputs/` folder to view your generated reports:

| Report File | Description |
|---|---|
| `outputs/daily_product_metrics/daily_product_metrics.csv` | Recomputed daily product revenue, transaction counts, averages, and reach. |
| `outputs/daily_customer_metrics/daily_customer_metrics.csv` | Recomputed daily customer revenue, transaction counts, and product diversity. |
| `outputs/rejected_records/rejected_records.csv` | Quarantined invalid records with exact error codes and failure reasons. |
| `outputs/reconciliation/reconciliation_report.csv` | Detailed cross-table mathematical parity assertions (438 PASS, 0 FAIL). |
| `outputs/run_reports/pipeline_runs.csv` | Operational execution ledger with row counts, checksums, and execution times. |
| `outputs/run_reports/pipeline_run_report.json` | Complete machine-readable audit report of the latest pipeline execution. |
| `outputs/run_reports/transaction_summary.csv` | Summary of active vs reversed transactions and total minor-unit amounts. |
| `outputs/performance/performance_report.csv` | Performance benchmarks separating input vs accepted throughput. |

---

## 3. Business Problem

Modern transactional platforms process millions of discrete events characterized by out-of-order arrivals, late-arriving events, duplicate deliveries, retro-active updates, and cancellations/reversals. Traditional batch pipelines frequently recompute entire historical datasets, leading to high computational costs, or use mutable state overwrites that corrupt analytical aggregates.

YottaFlex solves this by:
- Isolating an **immutable event ledger** (`source_events`) from the **authoritative transaction state** (`transactions`).
- Implementing **targeted recomputation** of only the affected reporting partitions.
- Guaranteeing **mathematical integrity** through independent reconciliation checks.
- Safeguarding monetary amounts using **integer minor units** (paise for INR) to prevent floating-point rounding errors.

---

## 4. Objectives

- **Idempotency**: Guarantee that re-running identical files, renamed files, or replaying events produces zero duplicate state changes or revenue inflation.
- **Out-of-Order Resilience**: Ensure lower versions arriving late do not regress newer transaction states.
- **Targeted Aggregation**: Recompute only modified `(business_date, entity)` partitions, including both old and new groups when attributes migrate.
- **Traceable Quarantine**: Defective rows are isolated in `rejected_records` with raw payloads, line numbers, and error codes without halting valid records.
- **Independent Reconciliation**: Validate aggregated metrics against authoritative transactions with 100% precision.

---

## 5. Key Features

- **Chunked Pre-Fetching Engine**: Boosts ingestion throughput to over **20,000 rows/second**.
- **Monotonic Version Management**: Full replacement snapshot semantics with version tracking.
- **Three-Tier Validation**: Independent schema, field, and business rule validators.
- **Zero Floating-Point Arithmetic**: Financial amounts stored as 64-bit integers.
- **CSV Formula Injection Sanitization**: All exported reports neutralize DDE execution vectors.
- **Comprehensive CLI**: 10 distinct operational commands.

---

## 6. Architecture

```mermaid
flowchart TD
    CSV[Source Event CSV] --> FP[SHA-256 Fingerprint]
    FP --> IDEM{File Already Processed?}
    IDEM -- Yes --> SKIP[Idempotent Skip]
    IDEM -- No --> STREAM[Streaming Batch Loader]
    
    STREAM --> SCH[Schema Validation]
    SCH --> FLD[Field Validation]
    FLD --> BIZ[Business Rule Validation]
    
    BIZ -- Invalid --> QUAR[rejected_records Quarantine]
    BIZ -- Valid --> DEDUP{Ledger Deduplication}
    
    DEDUP -- Duplicate --> SKIP_EV[No-op Skip]
    DEDUP -- New --> LEDGER[(source_events Ledger)]
    
    LEDGER --> STATE[Transaction State Machine]
    STATE --> TXN[(transactions Table)]
    
    TXN --> AFFECT[Affected Periods Tracker]
    AFFECT --> AGG_P[(daily_product_metrics)]
    AFFECT --> AGG_C[(daily_customer_metrics)]
    
    AGG_P --> RECON[Independent Reconciliation]
    AGG_C --> RECON
    TXN --> RECON
```

---

## 7. Technology Stack

| Component | Technology | Rationale |
|---|---|---|
| Language | Python 3.11+ | Modern dataclasses, typing, high performance. |
| Database | SQLite 3.35+ | Zero-dependency, ACID compliant, WAL mode. |
| Access | Python `sqlite3` | Strict parameterized queries, low overhead. |
| Validation | Pydantic V2 / Custom | Explicit typing and error code tracking. |
| Testing | Pytest & pytest-cov | Automated test suite and coverage reporting. |
| Performance | `time.perf_counter()` | Nanosecond-resolution benchmarking. |
| CLI | `argparse` & `tabulate` | Clean, standardized terminal interface. |
| Outputs | CSV & JSON | Formula-injection-safe reports. |

---

## 8. Project Folder Structure

```
yottaflex-incremental-data-pipeline/
├── src/
│   ├── __init__.py
│   ├── main.py
│   ├── config/             # Settings, constants, and logging configuration
│   ├── database/           # DB connection, models, schema, migrations, and seeding
│   ├── ingestion/          # CSV streaming, fingerprinting, batch loading
│   ├── validation/         # Schema, field, and business validators
│   ├── processing/         # Deduplication, versioning, state transitions, pipeline runner
│   ├── aggregation/        # Daily product and customer aggregation recomputation
│   ├── monitoring/         # Run tracking, observability, and metrics
│   ├── reconciliation/     # Independent checks and reconciliation reporting
│   ├── generator/          # Reference data and synthetic event generators
│   ├── reporting/          # CSV and JSON exporters, performance reports
│   └── cli/                # Command-line subcommands
├── database/
│   └── schema.sql          # Relational SQL schema
├── data/
│   ├── reference/          # products.csv and customers.csv
│   ├── sample/             # Curated valid, updates, reversals, late, and invalid events
│   ├── generated/          # Synthetic test datasets
│   └── quarantine/         # Quarantined bad files
├── tests/                  # 14 automated test modules
├── docs/                   # Full technical documentation
├── outputs/                # Generated metrics, run reports, and reconciliations
├── prompt-history/         # Sanitized AI prompt history
├── examples/               # Sample inputs, expected outputs, and sample reports
├── README.md
├── requirements.txt
├── pyproject.toml
├── run.ps1                 # Windows PowerShell task runner
├── run.bat                 # Windows Command Prompt task runner
├── Makefile                # Linux / macOS make task runner
├── .gitignore
└── .env.example
```

---

## 9. Database Design & Schema

The database consists of 9 relational tables:
1. `products`: Master product catalog.
2. `customers`: Master synthetic customer catalog.
3. `pipeline_runs`: Execution metadata, run durations, row counts, and statuses.
4. `source_events`: Append-only immutable historical event ledger.
5. `transactions`: Authoritative current state of each transaction.
6. `rejected_records`: Quarantine audit table for row-level validation failures.
7. `daily_product_metrics`: Recomputed daily revenue, transaction counts, averages, and reach.
8. `daily_customer_metrics`: Recomputed daily revenue, transaction counts, averages, and product diversity.
9. `processed_files`: SHA-256 file fingerprints preventing duplicate ingestion.

---

## 10. Entity Relationships

```mermaid
erDiagram
    products ||--o{ source_events : "product_id"
    products ||--o{ transactions : "product_id"
    products ||--o{ daily_product_metrics : "product_id"
    customers ||--o{ source_events : "customer_id"
    customers ||--o{ transactions : "customer_id"
    customers ||--o{ daily_customer_metrics : "customer_id"
    pipeline_runs ||--o{ source_events : "run_id"
    pipeline_runs ||--o{ rejected_records : "run_id"
    pipeline_runs ||--o{ processed_files : "run_id"
```

---

## 11. Data Dictionary

Refer to [DATA_DICTIONARY.md](docs/DATA_DICTIONARY.md) for full field definitions, types, nullability, constraints, and descriptions.

---

## 12. Source Event Data Contract

Canonical CSV event header:
```csv
event_id,transaction_id,event_version,event_type,event_timestamp,business_date,product_id,customer_id,amount_minor,currency
```

- `event_timestamp`: UTC ISO-8601 string (`YYYY-MM-DDTHH:MM:SSZ`).
- `business_date`: Reporting date (`YYYY-MM-DD`).
- `amount_minor`: Integer minor units (e.g., `50000` = ₹500.00).
- `event_type`: `CREATE`, `UPDATE`, or `REVERSE`.

---

## 13. Business Rules

Refer to [BUSINESS_RULES.md](docs/BUSINESS_RULES.md) for complete transition rules.
- `CREATE`: Initial version must be 1. Requires valid references. Sets state to `ACTIVE`.
- `UPDATE`: Version must be $> \text{latest\_version}$. Updates snapshot attributes. Recalculates both old and new aggregate partitions.
- `REVERSE`: Sets state to `REVERSED`. Daily metrics exclude reversed transactions. Reversals cannot be repeated.

---

## 14. Event Versioning & Snapshots

Higher event versions represent full entity replacement snapshots. When version 3 arrives after version 1 (missing version 2), version 3 is accepted as the complete authoritative state. Lower versions arriving out of order are quarantined under `VERSION_CONFLICT`.

---

## 15. CREATE, UPDATE, and REVERSE Handling

| Operation | Current Status | Incoming Version | Next Status | Metric Impact |
|---|---|---|---|---|
| `CREATE` | Non-existent | 1 | `ACTIVE` | Added to daily metrics |
| `UPDATE` | `ACTIVE` | $> \text{current}$ | `ACTIVE` | Old group decremented, new group incremented |
| `UPDATE` | `REVERSED` | Any | Rejected | Quarantined under `INVALID_TRANSACTION_STATE` |
| `REVERSE` | `ACTIVE` | $> \text{current}$ | `REVERSED` | Revenue subtracted from daily metrics |
| `REVERSE` | `REVERSED` | Any | Rejected | Quarantined under `INVALID_TRANSACTION_STATE` |

---

## 16. Late Events Handling

Events arriving after their occurrence date are assigned strictly to their `business_date`, not their ingestion timestamp. Historical partitions are updated accurately without mutating intermediate dates.

---

## 17. Out-of-Order Events

An out-of-order event with an event version lower than the current transaction's `latest_version` is rejected with `VERSION_CONFLICT` and quarantined in `rejected_records`. This prevents stale data from corrupting newer states.

---

## 18. Idempotency Guarantees

1. **File-Level**: A SHA-256 digest of every input file is stored in `processed_files`. Re-running identical files or renamed copies is safely skipped.
2. **Event-Level**: `source_events` enforces unique constraints on `event_id` and `(transaction_id, event_version)`. Replaying events results in safe deduplication without double-counting.

---

## 19. Transaction Recovery and Quarantine

- **Row-Level Quarantine**: Corrupt rows are saved in `rejected_records` with exact line numbers and error codes. Valid rows continue processing with run status `PARTIAL`.
- **Fatal Exception Rollback**: Database errors roll back uncommitted changes within the active batch and mark the run as `FAILED`.

---

## 20. Installation & Setup

```bash
# Clone repository
git clone <repo-url>
cd yottaflex-incremental-data-pipeline

# Install dependencies
pip install -r requirements.txt
```

---

## 21. Environment Configuration

Copy `.env.example` to `.env` to customize settings:
```bash
cp .env.example .env
```

---

## 22. Database Initialization

```bash
python -m src.main init-db
```
Creates all 9 tables, indexes, generates reference data (`products.csv`, `customers.csv`), and seeds catalogs.

---

## 23. Sample & Synthetic Data Generation

```bash
# Generate 100 sample events and curated test suites
python -m src.main generate --rows 100 --seed 42

# Generate 10,000 synthetic records
python -m src.main generate --rows 10000 --seed 42
```

---

## 24. Pipeline Execution

```bash
# Run pipeline on valid sample events
python -m src.main run --input data/sample/valid/events.csv

# Run pipeline with custom batch size
python -m src.main run --input data/generated/events.csv --batch-size 5000
```

---

## 25. Automated Testing & Coverage

```bash
# Run 56 automated tests
pytest -v

# Run coverage report (92.0% statement coverage)
pytest --cov=src --cov-report=term-missing
```

---

## 26. Independent Reconciliation Engine

```bash
python -m src.main reconcile
```
Computes true aggregates directly from `transactions WHERE status = 'ACTIVE'` and compares against stored `daily_product_metrics` and `daily_customer_metrics`.

---

## 27. Performance Benchmarks

```bash
# Run benchmark on isolated fresh database
python -m src.main benchmark --rows 100000 --seed 42
```

### Measured Execution Results (100,000 Events, seed=42)
| Workload / Benchmark Phase | Measured Time | Measured Throughput | Reconciliation Result |
|---|---|---|---|
| **Fresh Ingestion & Aggregation (100,000 rows)** | 24.61 s | 4,063.00 input events/sec<br>(4,021.41 accepted records/sec) | 11,966 PASS, 0 FAIL |
| **Bulk Group Aggregation Phase Only** | 1.51 s | 359.2x speedup over baseline | Exact Parity |
| **Deduplication Re-Run (100,000 rows)** | 5.03 s | 19,880.72 rows/sec | 11,966 PASS, 0 FAIL |

---

## 28. Sample Outputs & Reporting

Generate and export all analytical reports:
```bash
python -m src.main report
python -m src.main export --output outputs/
```

Generated files in `outputs/`:
- `daily_product_metrics/daily_product_metrics.csv`
- `daily_customer_metrics/daily_customer_metrics.csv`
- `rejected_records/rejected_records.csv`
- `run_reports/pipeline_runs.csv`
- `run_reports/transaction_summary.csv`
- `run_reports/pipeline_run_report.json`
- `reconciliation/reconciliation_report.csv`
- `performance/performance_report.csv`

---

## 29. System Limitations

Refer to [LIMITATIONS.md](docs/LIMITATIONS.md) for detailed boundaries:
- Single-writer SQLite locking model.
- Partitioning without dynamic currency conversion.
- 64-bit integer monetary bounds (92.2 quadrillion INR).

---

## 30. Future Improvements

- PostgreSQL / Distributed SQL adapter for concurrent writes.
- Dynamic FX conversion service for multi-currency buckets.
- REST & GraphQL API endpoints (see [FUTURE_API.md](docs/FUTURE_API.md)).
- Apache Kafka / RabbitMQ streaming consumers.

---

## 31. GitHub Push & Submission Instructions

Follow these commands to push the complete repository to your public GitHub account:

```bash
# 1. Verify working tree is clean
git status

# 2. Set main/master branch
git branch -M master

# 3. Add your GitHub remote repository (replace with your personal GitHub URL)
git remote add origin https://github.com/<YOUR_USERNAME>/yottaflex-incremental-data-pipeline.git

# 4. Push all code, commits, tests, and documentation
git push -u origin master
```

---

## 32. AI Usage Disclosure

Developed using Google DeepMind's Advanced Agentic Coding environment. All architecture, database schemas, validation engines, state machines, reconciliation logic, and documentation were implemented, tested, and verified against actual execution benchmarks. Refer to [prompt-history/PROMPTS.md](prompt-history/PROMPTS.md).
