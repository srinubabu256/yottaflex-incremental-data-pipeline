# YottaFlex Testing and Quality Assurance Strategy

## 1. Overview
The testing suite verifies the full behavioral, relational, and mathematical requirements of the YottaFlex pipeline. All automated tests run on isolated temporary SQLite databases instantiated with strict foreign keys, performance indexes, and seeded synthetic reference data.

---

## 2. Test Architecture and Fixtures

- **`temp_db` fixture**: Creates an isolated SQLite database file per test, executes `database/schema.sql`, generates synthetic reference catalogs (`products.csv`, `customers.csv`), and seeds them.
- **`create_event_csv` fixture**: Dynamic factory fixture allowing test functions to rapidly generate test CSVs with custom events or defective schemas.
- **Zero Shared State**: No test mutates production or persistent local databases.

---

## 3. Test Modules and Scenarios Covered

| Test Module | Coverage Scope |
|---|---|
| `test_database.py` | Schema initialization, 9 tables verification, foreign key constraint enforcement, unique constraints, index verification, migrations recording, and integrity checks. |
| `test_ingestion.py` | Streaming CSV reader, batch chunking, empty 0-byte file handling, missing file errors, schema validation, missing/unexpected headers, SHA-256 fingerprint consistency, Latin-1 fallback. |
| `test_validation.py` | Missing required fields, negative amounts, invalid timestamp syntax, unrecognised event types, unknown products, unknown customers. |
| `test_duplicate_events.py` | Exact duplicate event deduplication, no double-counting of revenue, conflicting payload quarantine under `DUPLICATE_EVENT`. |
| `test_event_versions.py` | `CREATE` requiring version 1, higher version arrival without intermediate versions (replacement snapshots), late lower version quarantine under `VERSION_CONFLICT`. |
| `test_transaction_updates.py` | Modifying amounts, business date shifting, product/customer changes, and rejecting `UPDATE` after terminal `REVERSE`. |
| `test_transaction_reversals.py` | Status transition to `REVERSED`, revenue exclusion from daily aggregates, rejecting repeated reversals without subtracting revenue twice. |
| `test_late_events.py` | Late events assigned to reporting `business_date` (not ingestion timestamp), out-of-order state preservation. |
| `test_idempotency.py` | Exact file re-run skip, renamed file re-run skip via checksum matching, zero duplicate state changes. |
| `test_recovery.py` | Row-level quarantine allowing valid records to proceed with `PARTIAL` status, database rollback and `FAILED` status logging on fatal exceptions. |
| `test_aggregation.py` | Daily product metrics, daily customer metrics, amount recalculations, group movement, obsolete group cleanup when all active transactions in partition are reversed. |
| `test_reconciliation.py` | Complete independent reconciliation matching 100% of active transactions (`PASS`), deliberate aggregate tampering detection (`FAIL`), foreign key audits. |
| `test_performance.py` | Verification of `time.perf_counter()` benchmark metrics collection, throughput calculations, and CSV reporting. |
| `test_cli.py` | End-to-end testing of all 10 CLI commands (`init-db`, `generate`, `run`, `reconcile`, `report`, `benchmark`, `runs`, `run-details`, `rejects`, `export`), error exit codes. |

---

## 4. Documented Domain-Specific Edge Cases

### Edge Case 1: Multi-Hop Attribute Migration
- **Location**: `tests/test_aggregation.py::test_domain_edge_case_multi_hop_attribute_migration`
- **Scenario**: A transaction migrates across `business_date`, `product_id`, and `customer_id` simultaneously across consecutive updates.
- **Verification**: Verifies that both old and new partitions are recomputed; the old partition drops to zero and its aggregate row is deleted, while the new partition is created with the updated revenue, maintaining total mathematical balance.

### Edge Case 2: Reversal with Concurrent Historical Late Arrival
- **Location**: `tests/test_reconciliation.py::test_domain_edge_case_reversal_with_concurrent_late_arrival`
- **Scenario**: A transaction is created at version 1 and reversed at version 2. An older/duplicate version 1 event arrives late out of order.
- **Verification**: Verifies that the late version 1 event is quarantined in `rejected_records` under `VERSION_CONFLICT`, does not resurrect the reversed transaction, and does not inject stale revenue into metrics.

---

## 5. Execution Commands

```bash
# Run all tests
pytest -v

# Run with test coverage
pytest --cov=src --cov-report=term-missing
```
