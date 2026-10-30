# YottaFlex System Limitations and Constraints

This document transparently records the known engineering boundaries, environmental assumptions, and trade-offs of the current YottaFlex implementation.

---

## 1. Concurrency and Multi-Writer Contention
- **SQLite Single-Writer Lock**: While SQLite WAL mode permits concurrent reads, write operations acquire an exclusive table-level write lock. Attempting high concurrency writes from multiple external operating system processes can cause `sqlite3.BusyError` if timeout thresholds (default 30s) are exceeded.
- **Recommended Scale**: Designed for single-worker sequential micro-batch processing or scheduled batch pipelines. For concurrent multi-worker write pipelines, migrating to PostgreSQL is recommended.

---

## 2. Currency Handling and Multi-Currency Aggregation
- **Single Currency Partitioning**: Financial amounts are stored as integer minor units (paise for INR). The system validates that currency matches supported lists (e.g., `INR`), but does not perform dynamic foreign exchange conversion between different currencies within the same product or customer daily aggregate bucket.
- **Cross-Currency Assumption**: Transactions aggregated into a given product partition are assumed to be denominated in the pipeline's configured default currency (`INR`).

---

## 3. Financial Numeric Precision Bounds
- **64-Bit Integer Capacity**: SQLite integers are stored as signed 64-bit values (maximum value: $2^{63} - 1 \approx 9.22 \times 10^{18}$ paise, or approximately 92.2 quadrillion INR). Aggregate calculations will remain mathematically exact up to this limit; exceeding this will cause integer overflow.

---

## 4. File-Level Ingestion and Filesystem Coupling
- **Local File Paths**: Ingestion reads directly from local file paths or mounted storage volumes. Cloud object stores (such as AWS S3, Google Cloud Storage, or Azure Blob Storage) require local staging or pre-downloading before invoking `python -m src.main run --input ...`.

---

## 5. Intermediate Snapshot Version Gaps
- **Replacement Snapshot Assumption**: If version 3 arrives after version 1 (missing version 2), YottaFlex assumes that version 3 contains the full, authoritative current state of the transaction. Partial delta patches (e.g. "increment amount by 100") are not supported without complete entity attribute snapshots.
