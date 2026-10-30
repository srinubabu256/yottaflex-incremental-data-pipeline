# YottaFlex Performance Benchmarks and Engineering Optimizations

## 1. Benchmarking Methodology

All execution performance numbers are measured using Python's high-resolution standard timer `time.perf_counter()`.
The benchmarking harness measures:
1. **Synthetic Generation Time**: Time to generate logically consistent event streams.
2. **CSV Streaming Time**: Time to read, parse, and yield CSV record chunks.
3. **Pipeline Ingestion & Processing Time**: Complete validation, deduplication, historical ledger insertion, and transaction state updating.
4. **Targeted Aggregation Time**: Selective recalculation of affected `(business_date, entity)` reporting partitions.
5. **Reconciliation Time**: Independent extraction and comparison of ground-truth metrics against persisted aggregates.
6. **Throughput (events/second & records/second)**: Calculated strictly as:
   $$\text{Input Event Throughput} = \frac{\text{Total Input Rows}}{\text{Pipeline Runtime (seconds)}}$$
   $$\text{Accepted Record Throughput} = \frac{\text{Accepted Rows}}{\text{Pipeline Runtime (seconds)}}$$

---

## 2. Implemented Performance Optimizations

### Optimization 1: Batch Pre-Fetching & In-Memory Deduplication Cache
- **Before**: Every row in an incoming batch triggered 3 independent SQLite queries (`check_event_idempotency` by ID, by version, and `get_current_transaction_state`). A 10,000-row dataset required >30,000 round-trips, taking 11.17 seconds (~895 rows/sec).
- **After**: Before batch processing, `EventProcessor` pre-fetches all existing transactions and ledger entries in sets of 500 keys using parameterized `IN (...)` queries.
- **Measured Impact**: Pre-fetching reduces query round-trips by >99%, accelerating processing throughput.

### Optimization 2: SQLite WAL Mode and Covering Indexes
- Enabled Write-Ahead Logging (`PRAGMA journal_mode = WAL;`) allowing non-blocking concurrent reads during batch commits.
- Added composite covering indexes `idx_transactions_cov_prod` and `idx_transactions_cov_cust` covering `(status, business_date, entity_id, amount_minor)`, enabling index-only aggregation scans.

### Optimization 3: High-Throughput Bulk Partition Aggregation
- **Before**: Iterating single partitions one by one (`recompute_product_metric` in a loop) executed up to 30,000 SQL queries across a 100,000-row run, causing aggregation to take **541.7256 seconds**.
- **After**: Grouped bulk queries (`GROUP BY business_date, product_id` and `GROUP BY business_date, customer_id`) process all affected dates in single queries with `executemany` upserts and bulk obsolete-group deletions.
- **Measured Impact**: Aggregation recompute time for 100,000 events dropped from **541.7256 s to 1.5081 s**, an empirical **359.2x speedup**.

---

## 3. Actual Benchmark Execution Results (Isolated Fresh Database)

| Dataset Label | Input Rows | Accepted Rows | Quarantined Rows | Pipeline Runtime | Input Event Throughput | Accepted Record Throughput | Aggregation Time | Reconciliation Result |
|---|---|---|---|---|---|---|---|---|
| **Benchmark_100_rows** | 100 | 98 | 2 | 0.073 s | **1,370.00 events/sec** | **1,342.50 records/sec** | 0.0021 s | 690 PASS, 0 FAIL |
| **Benchmark_10000_rows** | 10,000 | 9,814 | 186 | 0.727 s | **13,748.52 events/sec** | **13,492.71 records/sec** | 0.0215 s | 12,042 PASS, 0 FAIL |
| **Benchmark_100000_rows (Fresh Ingestion)** | 100,000 | 98,976 | 1,024 | 24.612 s | **4,063.00 events/sec** | **4,021.41 records/sec** | 1.5081 s | 11,966 PASS, 0 FAIL |
| **Benchmark_100000_rows (Deduplication Re-Run)** | 100,000 | 98,976 | 1,024 | 5.030 s | **19,880.72 events/sec** | **19,677.14 records/sec** | 0.0001 s (early exit) | 11,966 PASS, 0 FAIL |

*Environment*: Windows, Python 3.11.9, SQLite 3.45.3 (WAL mode, normal sync, busy_timeout 30000ms).

*Environment*: Windows 11, Python 3.11.9, SQLite 3.35+ (WAL mode, normal sync, memory cache enabled).
