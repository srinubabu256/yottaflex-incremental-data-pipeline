# YottaFlex Architectural Design Decisions

This document articulates the core engineering trade-offs, architectural decisions, and technology choices adopted in the implementation of the YottaFlex Incremental Data Engineering Pipeline.

---

## 1. Database Engine: SQLite with WAL vs ORMs / Distributed Databases

### Decision
Use standard Python `sqlite3` with strict parameterized SQL, Write-Ahead Logging (`PRAGMA journal_mode = WAL;`), and foreign key enforcement (`PRAGMA foreign_keys = ON;`). Avoid heavy ORMs (like Django ORM or complex SQLAlchemy abstractions).

### Rationale
- **Zero Overhead**: In local pipeline execution, SQLite provides sub-millisecond execution times without network round-trip overhead.
- **ACID Compliance**: SQLite in WAL mode allows concurrent readers alongside a serial writer with atomic transaction guarantees (`BEGIN IMMEDIATE` and rollback).
- **Portability**: Fully zero-dependency and local, running identically across platforms without requiring daemon setups or external cloud infrastructure.
- **SQL Portability**: All queries use standard SQL syntax (ANSI SQL / SQLite 3.35+ compatible) with parameterized queries (`?`), facilitating a straightforward migration path to PostgreSQL when cloud scaling is required.

---

## 2. Monetary Arithmetic: Integer Minor Units (Paise) vs Floating-Point Decimals

### Decision
Store all financial values as 64-bit integers representing minor currency units (e.g., 1 INR = 100 paise; 500.25 INR stored as 50025).

### Rationale
- **Elimination of IEEE 754 Floating-Point Inaccuracies**: Floating-point representations introduce rounding artifacts (e.g. $0.1 + 0.2 = 0.30000000000000004$) which are unacceptable in financial accounting and reconciliation.
- **Performance**: Integer arithmetic in CPU registers and database engines is substantially faster than decimal or string-based decimal calculations.
- **Mathematical Exactness**: Division for average transaction calculations uses integer floor division (`total_revenue // count`), ensuring deterministic equality across reconciliations.

---

## 3. Ingestion Strategy: Chunked Pre-Fetching vs Row-by-Row Execution

### Decision
Implement chunked pre-fetching within configurable batches (default 5,000 rows). Pre-fetch existing transactions and ledger entries in sets of 500 keys using parameterized SQL (`IN (?, ?, ...)`).

### Rationale
- **Round-Trip Reduction**: Processing 10,000 rows row-by-row requires over 30,000 discrete SQL queries, incurring severe execution latency (11+ seconds).
- **Throughput Optimization**: Pre-fetching reduces query count to ~60 batch queries, boosting throughput from ~895 rows/sec to **over 20,500 rows/sec** (a 23x performance gain).
- **Memory Predictability**: Chunks of 5,000 rows consume under 15MB RAM, ensuring safe execution on memory-constrained systems without full-file in-memory loading.

---

## 4. Aggregation Architecture: Targeted Recomputation vs Full Historical Recalculation

### Decision
Track fine-grained `(business_date, product_id)` and `(business_date, customer_id)` partitions affected by each event batch. Only recalculate these specific aggregate rows. Furthermore, when an `UPDATE` shifts dates or entities, track both old and new groups.

### Rationale
- **Scalability**: Recomputing all historical aggregations on every incoming micro-batch scales as $\mathcal{O}(N_{\text{total\_history}})$, which rapidly becomes a bottleneck. Targeted recomputation scales as $\mathcal{O}(N_{\text{affected\_partitions}})$.
- **Mathematical Correctness**: When a transaction moves from date $D_1$ to date $D_2$, evaluating only $D_2$ leaves ghost revenue on $D_1$. Recalculating both old and new groups guarantees perfect reconciliation.
- **Obsolete Partition Cleanup**: If all transactions in a group are reversed or moved, deleting the obsolete aggregate record ensures accurate entity counts and avoids reporting zero-revenue partitions.

---

## 5. Security & CSV Formula Injection Protection

### Decision
Sanitize all string values exported to CSV by prefixing cells that begin with formula indicators (`=`, `+`, `-`, `@`, `\t`, `\r`) with a single quotation mark (`'`).

### Rationale
- **Spreadsheet Security**: Unsanitized user inputs opened in spreadsheet tools (Microsoft Excel, Google Sheets, LibreOffice Calc) can trigger dynamic formula execution (DDE / CSV Injection attacks) that execute unauthorized external commands.
- **Defensive Engineering**: Sanitization guarantees that exported reporting files remain safe for consumption by business analysts.
