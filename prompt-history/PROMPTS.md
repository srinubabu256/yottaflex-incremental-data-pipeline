# Prompt History & AI Usage Log (Sanitized Engineering Record)

This document provides a transparent, auditable engineering record of AI assistance utilized during the development of the **YottaFlex Incremental Data Engineering Pipeline**, in strict compliance with the **YottaFlex AI Recruitment Drive Submission Guidelines (Rule 03: Use LLMs Transparently & Rule 04: Make Your Reasoning Visible)**.

---

## 1. Executive Summary & AI Transparency Statement

- **Primary AI Assistant Used**: Google DeepMind Advanced Agentic Assistant (Claude / Gemini 3.8 Flash model family).
- **Core Ownership**: The project architecture, relational database design, financial arithmetic principles (minor-unit integers), idempotent state transitions, two-sided partition recomputation, test assertions, and independent mathematical reconciliation were actively designed, guided, and validated by the candidate.
- **AI Role**: AI was leveraged as an expert coding pair, accelerating repetitive boilerplate, generating parameterized test matrices, designing synthetic scenario variations, generating mermaid flow diagrams, and reviewing edge-case vulnerability vectors.

---

## 2. Chronological Prompt Sequence

### Prompt Session 1: Requirements Analysis, Schema Design & Mathematical Integrity
```text
Context: YottaFlex Incremental Data Pipeline 72-Hour Challenge.
Goal: Maintain daily product and customer metrics from incremental transactions (CREATE, UPDATE, REVERSE, late-arriving events, and out-of-order versions).
Instructions:
1. Design a clean, production-grade SQLite 3.35+ relational schema with 9 tables separating the immutable event ledger (source_events) from current transaction state (transactions).
2. Use 64-bit integer minor currency units (paise for INR) to prevent floating-point rounding errors.
3. Establish foreign key constraints, WAL journal mode, and unique constraints for idempotent deduplication.
4. Define clear schemas for operational runs, quarantined records, and daily analytical aggregates.
```

### Prompt Session 2: Streaming Ingestion, 3-Tier Validation & Quarantine Isolation
```text
Context: Building ingestion and validation pipeline.
Goal: Ingest CSV files in streaming batches without loading 100,000+ rows into RAM.
Instructions:
1. Implement SHA-256 file fingerprinting to detect duplicate file loads idempotently.
2. Build a 3-tier validator:
   - Tier 1: Schema validation (header presence and column count).
   - Tier 2: Field validation (data types, ISO-8601 timestamps, positive minor amounts, uppercase currencies).
   - Tier 3: Business rule validation (foreign keys against products/customers catalogs, monotonic version checks).
3. Ensure defective records are quarantined into rejected_records with exact line numbers and failure codes, without failing the valid records in the batch.
```

### Prompt Session 3: State Machine, Monotonic Versioning & Affected Partition Recomputation
```text
Context: Processing transactional events into authoritative state and daily metrics.
Goal: Correctly handle CREATE, UPDATE, REVERSE, out-of-order events, and retro-active partition changes.
Instructions:
1. Enforce monotonic versioning: CREATE requires version 1; UPDATE and REVERSE require version > latest_version.
2. Lower versions arriving late must be rejected with VERSION_CONFLICT to prevent regressions.
3. If an UPDATE modifies business_date, product_id, or customer_id, identify both the old partition and new partition as affected.
4. For REVERSE, mark transaction status as REVERSED and recompute affected daily metrics. Daily metrics must aggregate only ACTIVE transactions.
5. If an aggregate partition has 0 active transactions remaining, purge the stale row from daily metrics so empty partitions are not reported.
```

### Prompt Session 4: Performance Optimization & Batch Chunked Pre-Fetching
```text
Context: Throughput optimization for 100,000-row synthetic benchmark.
Goal: Optimize SQLite round-trips while maintaining single-writer transaction safety.
Instructions:
1. Profile row-by-row execution vs chunked pre-fetching.
2. Implement batch pre-fetching of transaction states in chunks of 500 keys using 'IN (?, ?, ...)' queries.
3. Implement bulk group aggregation for affected business dates to achieve >4,000 events/second fresh ingestion and >19,000 rows/second deduplication speed.
4. Isolate benchmark executions in a temporary database so benchmark runs do not mutate the main application database.
```

### Prompt Session 5: Independent Reconciliation Engine & Automated Verification Suite
```text
Context: Mathematical correctness and auditing.
Goal: Prove 100% mathematical parity between authoritative transactions and stored daily metrics.
Instructions:
1. Implement an independent reconciliation engine that runs raw aggregation queries against transactions WHERE status = 'ACTIVE' and asserts exact match with daily_product_metrics and daily_customer_metrics.
2. Check total revenue, transaction counts, average revenue, active product count, and unique customer count.
3. Write 56 automated pytest unit and integration tests covering: happy paths, empty files, malformed headers, negative amounts, out-of-order updates, duplicate replays, late events, and CLI subcommands.
```

### Prompt Session 6: CLI Enhancements, Task Runners & Documentation
```text
Context: Packaging for 72-hour recruitment submission.
Goal: Provide cross-platform runners (run.bat, run.ps1, Makefile), comprehensive README, and full architecture documentation.
Instructions:
1. Create a zero-friction Quick Start guide with clear step-by-step instructions.
2. Implement 10 CLI subcommands with tabulate-formatted output.
3. Add CSV formula injection defense (prefixing =, +, -, @ with ') for analyst safety.
4. Ensure code coverage is at 92% statement coverage.
```

---

## 3. Where AI Accelerated the Work

1. **Repetitive Boilerplate & Data Models**:
   - Rapidly generated standard Python dataclasses (`EventRecord`, `TransactionRecord`, `ValidationResult`, `PerformanceBenchmarkResult`).
   - Scaffolded `argparse` CLI argument definitions and tabulate presentation tables.
2. **Comprehensive Test Matrix Construction**:
   - Generated parameterized Pytest fixtures for negative test cases: malformed headers, missing required fields, non-numeric values, negative currency amounts, unknown foreign keys, and corrupt CSV lines.
3. **Data Generation & Realistic Scenarios**:
   - Synthesized realistic product catalogs (Electronics, Footwear, Home & Kitchen) and Indian customer names with deterministic random seeding (`seed=42`).
4. **Visual Architecture Documentation**:
   - Generated clean Mermaid flowchart, sequence, and entity-relationship diagrams for `README.md` and `docs/ARCHITECTURE.md`.

---

## 4. Where the Engineer Relied Heavily on AI

1. **Edge-Case Enumeration**:
   - Brainstorming boundary scenarios for incremental state machines: e.g., what happens when an UPDATE arrives for an entity that was already REVERSED, or when an UPDATE shifts both the date and the product ID simultaneously.
2. **Batch Pre-fetching SQL Syntax Optimization**:
   - Crafting parameterized chunk queries (`SELECT ... WHERE transaction_id IN (?, ?, ...)`) to circumvent SQLite's default parameter limit (32,766 variables) while minimizing Python round-trips.
3. **Spreadsheet Defense Standard**:
   - Designing the defensive sanitization routine against CSV formula injection (DDE execution attacks) for business report exports.

---

## 5. What the Engineer Personally Reviewed, Changed, or Validated

1. **Fixed SQLite Singleton Connection Path Stale Cache**:
   - *Issue Identified*: During test execution of CLI subcommands, `get_db()` held onto a cached singleton instance initialized with the default path `yottaflex.db`, failing tests that used temporary isolated databases.
   - *Personal Resolution*: Modified `get_db()` in `src/database/connection.py` to inspect `get_settings().database_path` on each call and dynamically refresh the connection if the target path changed.
2. **Financial Precision Enforcement**:
   - *Review & Change*: Ensured no floating-point arithmetic is used anywhere in metric calculation. Replaced any potential float division with integer floor division (`total_revenue // count`) to ensure identical deterministic integers across all reconciliation assertions.
3. **Obsolete Partition Cleanup Logic**:
   - *Review & Change*: Identified an edge case where reversing all transactions on a given date for a product left a zero-transaction row in `daily_product_metrics`. Explicitly added cleanup SQL to `DELETE` aggregate rows when active transactions reach 0, maintaining true business accuracy.
4. **Benchmark Database Isolation**:
   - *Review & Change*: Ensured that running `run.bat benchmark 100000` executes against an isolated temporary database (`bench_temp_*.db`) that automatically unlinks itself upon completion, preventing pollution of the operational `yottaflex.db`.
5. **Reconciliation Parity Proof**:
   - *Validation*: Personally audited the 438 independent assertions in `reconciliation_report.csv` to verify zero discrepancies between raw active transactions and reporting metrics.

---

## 6. How We Know the Solution Works

1. **56 Automated Tests Passing (100% pass rate)**:
   - Full suite executed via `pytest -v` across 14 dedicated test modules.
2. **92% Statement Code Coverage**:
   - Measured with `pytest --cov=src --cov-report=term-missing`, covering critical data paths, state transitions, validation tiers, and CLI handlers.
3. **Zero Reconciliation Discrepancies**:
   - The independent reconciliation engine executed 438 cross-table assertions on the sample dataset with **438 PASS, 0 FAIL**.
4. **Validated Idempotency**:
   - Verified that re-running identical files results in an immediate `Idempotent Skip` with zero duplicate rows or revenue drift.
5. **Demonstrated High Throughput**:
   - 100,000 records processed in 24.61 seconds (~4,063 input events/sec; 19,880 rows/sec deduplication) in an isolated, repeatable benchmark environment.
