# YottaFlex Future REST API Specification (Frontend Integration Ready)

## 1. Overview
As specified in Section 24 of the architecture requirements, the YottaFlex backend services are designed for seamless integration with future REST/GraphQL APIs and web frontends. This document specifies the future API contracts.

> **Note**: These are future integration specifications. Core services are already modular and structured to directly back these endpoints without modifying business logic.

---

## 2. API Endpoints

### 2.1 Health and Summary
- **`GET /api/health`**
  - **Description**: Returns database connectivity and schema integrity status.
  - **Response**: `{"status": "healthy", "database": "connected", "integrity": "ok"}`
- **`GET /api/dashboard/summary`**
  - **Description**: High-level KPI summary (total revenue, active transactions, reversed transactions, total runs, rejected records).
  - **Response**:
    ```json
    {
      "active_transactions_count": 85000,
      "total_revenue_minor": 850000000,
      "reversed_transactions_count": 5000,
      "total_runs": 15,
      "total_quarantined": 150
    }
    ```

### 2.2 Metrics Analytics
- **`GET /api/metrics/products`**
  - **Query Params**: `business_date`, `product_id`, `limit`, `offset`
  - **Response**: List of daily product metrics with revenue, transaction count, average amount, and distinct customer reach.
- **`GET /api/metrics/customers`**
  - **Query Params**: `business_date`, `customer_id`, `limit`, `offset`
  - **Response**: List of daily customer metrics with revenue, transaction count, average amount, and distinct product diversity.

### 2.3 Pipeline Operations & Observability
- **`GET /api/pipeline/runs`**
  - **Query Params**: `limit`, `status`
  - **Response**: List of historical pipeline runs with duration, input rows, accepted, rejected, and statuses.
- **`GET /api/pipeline/runs/{run_id}`**
  - **Response**: Detailed execution breakdown of a specific pipeline run.
- **`GET /api/pipeline/rejections`**
  - **Query Params**: `run_id`, `rejection_code`, `limit`
  - **Response**: List of quarantined records with source file, row number, event ID, raw payload, and failure reason.
- **`POST /api/pipeline/run`**
  - **Payload**: `{"file_path": "data/sample/valid/events.csv", "batch_size": 5000}`
  - **Response**: `PipelineRunResult` JSON.
- **`POST /api/pipeline/backfill`**
  - **Payload**: `{"start_date": "2026-10-01", "end_date": "2026-10-25"}`
  - **Description**: Triggers targeted recomputation of historical date partitions.

### 2.4 Reconciliation & Performance
- **`GET /api/reconciliation`**
  - **Response**: Latest reconciliation check summary, passed count, failed count, and detailed audit check rows.
- **`GET /api/performance`**
  - **Response**: Benchmark execution history, throughput rates, and timing distributions.
