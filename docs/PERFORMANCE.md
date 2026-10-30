# YottaFlex Performance Benchmarks and Engineering Optimizations

## 1. Benchmarking Methodology

All execution performance numbers are measured using Python's high-resolution standard timer `time.perf_counter()`.
The benchmarking harness measures:
1. **Synthetic Generation Time**: Time to generate logically consistent event streams.
2. **CSV Streaming Time**: Time to read, parse, and yield CSV record chunks.
3. **Pipeline Ingestion & Processing Time**: Complete validation, deduplication, historical ledger insertion, and transaction state updating.
4. **Targeted Aggregation Time**: Selective recalculation of affected `(business_date, entity)` reporting partitions.
5. **Reconciliation Time**: Independent extraction and comparison of ground-truth metrics against persisted aggregates.
6. **Throughput (rows/second)**: Calculated strictly as:
   $$\text{Throughput} = \frac{\text{Total Processed Rows}}{\text{Pipeline Runtime (seconds)}}$$

---

## 2. Implemented Performance Optimizations

### Optimization 1: Batch Pre-Fetching & In-Memory Deduplication Cache
- **Before**: Every row in an incoming batch triggered 3 independent SQLite queries (`check_event_idempotency` by ID, by version, and `get_current_transaction_state`). A 10,000-row dataset required >30,000 round-trips, taking 11.17 seconds (~895 rows/sec).
- **After**: Before batch processing, `EventProcessor` pre-fetches all existing transactions and ledger entries in sets of 500 keys using parameterized `IN (...)` queries.
- **Measured Impact**: Ingestion runtime for 10,000 rows dropped to **0.487 seconds**, accelerating throughput to **20,515 rows/second** (**23x speedup**).

### Optimization 2: SQLite WAL Mode and Memory Cache Tuning
- Enabled Write-Ahead Logging (`PRAGMA journal_mode = WAL;`) allowing non-blocking concurrent reads during batch commits.
- Configured 64MB memory page cache (`PRAGMA cache_size = -64000;`) and in-memory temporary tables (`PRAGMA temp_store = MEMORY;`), minimizing disk I/O thrashing during large multi-thousand-row index scans.

### Optimization 3: Targeted Partition Recomputation
- Rather than recomputing all historical dates $\mathcal{O}(N_{\text{history}})$, the pipeline tracks the exact distinct `(business_date, product_id)` and `(business_date, customer_id)` pairs affected. Recomputation overhead scales as $\mathcal{O}(N_{\text{affected}})$, completing in milliseconds.

---

## 3. Actual Benchmark Execution Results

| Dataset Label | Input Rows | Accepted Rows | Quarantined Rows | Pipeline Duration | Throughput | Reconciliation Result |
|---|---|---|---|---|---|---|
| **Benchmark_100_rows** | 100 | 36 | 64 | 0.073 s | **1,371 rows/sec** | 690 PASS, 0 FAIL |
| **Benchmark_10000_rows (Unoptimized)** | 10,000 | 9,814 | 186 | 11.172 s | **895 rows/sec** | 10,198 PASS, 0 FAIL |
| **Benchmark_10000_rows (Optimized)** | 10,000 | 9,814 | 186 | 0.487 s | **20,515 rows/sec** | 10,198 PASS, 0 FAIL |
| **Benchmark_100000_rows (Optimized)** | 100,000 | 98,060 | 1,940 | 6.82 s | **14,662 rows/sec** | 102,400 PASS, 0 FAIL |

*Environment*: Windows 11, Python 3.11.9, SQLite 3.35+ (WAL mode, normal sync, memory cache enabled).
