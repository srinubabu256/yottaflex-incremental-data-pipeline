# YottaFlex Operations and Deployment Manual

This manual provides operational instructions for managing, monitoring, debugging, and maintaining the YottaFlex Incremental Data Pipeline in production environments.

---

## 1. Setup and Environment Initialization

### 1.1 Prerequisites
- Python 3.11+
- SQLite 3.35+ (standard with Python 3.11)
- Git

### 1.2 Installation
```bash
# Clone repository
git clone <repo-url>
cd yottaflex-incremental-data-pipeline

# Create virtual environment
python -m venv .venv
# Activate on Windows:
.venv\Scripts\activate
# Activate on Linux/macOS:
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 1.3 Database Initialization
```bash
# Initializes 9 tables, indexes, and reference catalogs
python -m src.main init-db
```

---

## 2. CLI Command Reference

| Command | Usage | Description |
|---|---|---|
| `init-db` | `python -m src.main init-db` | Initializes SQLite schema and seeds reference catalogs. |
| `generate` | `python -m src.main generate --rows 1000 --seed 42` | Generates reproducible synthetic transaction events. |
| `run` | `python -m src.main run --input <path> [--batch-size 5000]` | Ingests and processes transaction events CSV file. |
| `reconcile` | `python -m src.main reconcile` | Executes independent reconciliation checks between raw txns and metrics. |
| `report` | `python -m src.main report` | Exports all analytical CSVs and JSON run reports to `outputs/`. |
| `benchmark` | `python -m src.main benchmark --rows 100000` | Measures actual execution duration, throughput, and reconciliation. |
| `runs` | `python -m src.main runs [--limit 20]` | Lists recent pipeline execution runs and statuses. |
| `run-details` | `python -m src.main run-details --run-id <run-id>` | Displays comprehensive metrics for a specific pipeline run. |
| `rejects` | `python -m src.main rejects [--run-id <run-id>]` | Lists quarantined records, row numbers, and error reasons. |
| `export` | `python -m src.main export [--output <dir>]` | Exports formula-injection-safe CSV tables to output directory. |

---

## 3. Monitoring, Troubleshooting, and Recovery

### 3.1 Interpreting Pipeline Run Statuses
- **`SUCCESS`**: All input records were valid, processed, and applied without quarantine.
- **`PARTIAL`**: At least one record was quarantined in `rejected_records`. All valid rows were processed and committed.
- **`FAILED`**: A fatal database or system exception occurred. Any uncommitted state changes in the active batch were rolled back.

### 3.2 Quarantine Inspection and Remediation
When a run reports `PARTIAL`:
```bash
# Identify the rejected rows
python -m src.main rejects --run-id <RUN_ID>
```
Inspect the `rejection_code` and `rejection_reason`. Correct the data at the source, or prepare a remediated micro-batch for ingestion.

### 3.3 Safe Retries and Idempotency
- Re-running the pipeline on an already processed file is safe. The pipeline checks the file's SHA-256 fingerprint in `processed_files` and skips execution with status `SUCCESS` and `is_idempotent_skip: True`.
- Re-running a renamed file with identical contents is also recognized via checksum and safely skipped.

---

## 4. Backup and Restore Procedures

### 4.1 SQLite Backup (Online Safe)
To create a safe online backup without stopping readers:
```bash
# Using SQLite backup command
sqlite3 yottaflex.db ".backup 'backup_yottaflex_$(date +%Y%m%d).db'"
```

### 4.2 Restoring from Backup
```bash
cp backup_yottaflex_20261030.db yottaflex.db
python -m src.main reconcile
```
