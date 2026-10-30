"""
Independent reconciliation verification checks.
Compares actual persisted metrics with expected values calculated from authoritative transactions.
"""

import sqlite3
from dataclasses import dataclass
from src.reconciliation.source_comparison import (
    get_expected_product_metrics,
    get_expected_customer_metrics,
)


@dataclass
class ReconciliationCheckRow:
    metric_type: str        # PRODUCT, CUSTOMER, INTEGRITY
    business_date: str
    entity_id: str
    metric_name: str
    expected_value: str
    actual_value: str
    difference: str
    status: str             # PASS or FAIL
    explanation: str

    def to_dict(self) -> dict:
        return {
            "metric_type": self.metric_type,
            "business_date": self.business_date,
            "entity_id": self.entity_id,
            "metric_name": self.metric_name,
            "expected_value": self.expected_value,
            "actual_value": self.actual_value,
            "difference": self.difference,
            "status": self.status,
            "explanation": self.explanation,
        }


def run_product_metric_checks(conn: sqlite3.Connection) -> list[ReconciliationCheckRow]:
    """Reconciles daily_product_metrics against authoritative state."""
    expected_map = get_expected_product_metrics(conn)

    # Actual from table
    cur = conn.execute("SELECT * FROM daily_product_metrics;")
    actual_map = {
        (row["business_date"], row["product_id"]): dict(row)
        for row in cur.fetchall()
    }

    rows: list[ReconciliationCheckRow] = []
    all_keys = set(expected_map.keys()) | set(actual_map.keys())

    metrics_to_check = [
        "transaction_count",
        "total_revenue_minor",
        "average_amount_minor",
        "customer_count",
    ]

    for b_date, p_id in sorted(all_keys):
        exp = expected_map.get((b_date, p_id))
        act = actual_map.get((b_date, p_id))

        if exp is None and act is not None:
            # Unexpected group
            rows.append(
                ReconciliationCheckRow(
                    metric_type="PRODUCT",
                    business_date=b_date,
                    entity_id=p_id,
                    metric_name="group_presence",
                    expected_value="ABSENT",
                    actual_value="PRESENT",
                    difference="Unexpected group in aggregate table",
                    status="FAIL",
                    explanation="Metric exists in daily_product_metrics but has no active transactions.",
                )
            )
            continue

        if exp is not None and act is None:
            # Missing group
            rows.append(
                ReconciliationCheckRow(
                    metric_type="PRODUCT",
                    business_date=b_date,
                    entity_id=p_id,
                    metric_name="group_presence",
                    expected_value="PRESENT",
                    actual_value="ABSENT",
                    difference="Missing group in aggregate table",
                    status="FAIL",
                    explanation="Active transactions exist but aggregate row was not found.",
                )
            )
            continue

        # Both present, check metric values
        for m in metrics_to_check:
            exp_val = exp[m]
            act_val = act[m]
            diff = act_val - exp_val
            status = "PASS" if diff == 0 else "FAIL"
            explanation = (
                f"{m} matches authoritative transactions."
                if status == "PASS"
                else f"Mismatch: expected {exp_val}, actual {act_val}."
            )
            rows.append(
                ReconciliationCheckRow(
                    metric_type="PRODUCT",
                    business_date=b_date,
                    entity_id=p_id,
                    metric_name=m,
                    expected_value=str(exp_val),
                    actual_value=str(act_val),
                    difference=str(diff),
                    status=status,
                    explanation=explanation,
                )
            )

    return rows


def run_customer_metric_checks(conn: sqlite3.Connection) -> list[ReconciliationCheckRow]:
    """Reconciles daily_customer_metrics against authoritative state."""
    expected_map = get_expected_customer_metrics(conn)

    # Actual from table
    cur = conn.execute("SELECT * FROM daily_customer_metrics;")
    actual_map = {
        (row["business_date"], row["customer_id"]): dict(row)
        for row in cur.fetchall()
    }

    rows: list[ReconciliationCheckRow] = []
    all_keys = set(expected_map.keys()) | set(actual_map.keys())

    metrics_to_check = [
        "transaction_count",
        "total_revenue_minor",
        "average_amount_minor",
        "product_count",
    ]

    for b_date, c_id in sorted(all_keys):
        exp = expected_map.get((b_date, c_id))
        act = actual_map.get((b_date, c_id))

        if exp is None and act is not None:
            rows.append(
                ReconciliationCheckRow(
                    metric_type="CUSTOMER",
                    business_date=b_date,
                    entity_id=c_id,
                    metric_name="group_presence",
                    expected_value="ABSENT",
                    actual_value="PRESENT",
                    difference="Unexpected group in aggregate table",
                    status="FAIL",
                    explanation="Metric exists in daily_customer_metrics but has no active transactions.",
                )
            )
            continue

        if exp is not None and act is None:
            rows.append(
                ReconciliationCheckRow(
                    metric_type="CUSTOMER",
                    business_date=b_date,
                    entity_id=c_id,
                    metric_name="group_presence",
                    expected_value="PRESENT",
                    actual_value="ABSENT",
                    difference="Missing group in aggregate table",
                    status="FAIL",
                    explanation="Active transactions exist but aggregate row was not found.",
                )
            )
            continue

        for m in metrics_to_check:
            exp_val = exp[m]
            act_val = act[m]
            diff = act_val - exp_val
            status = "PASS" if diff == 0 else "FAIL"
            explanation = (
                f"{m} matches authoritative transactions."
                if status == "PASS"
                else f"Mismatch: expected {exp_val}, actual {act_val}."
            )
            rows.append(
                ReconciliationCheckRow(
                    metric_type="CUSTOMER",
                    business_date=b_date,
                    entity_id=c_id,
                    metric_name=m,
                    expected_value=str(exp_val),
                    actual_value=str(act_val),
                    difference=str(diff),
                    status=status,
                    explanation=explanation,
                )
            )

    return rows


def run_integrity_reconciliation(conn: sqlite3.Connection) -> list[ReconciliationCheckRow]:
    """Runs relational and ledger integrity checks."""
    rows = []

    # 1. Foreign Key Integrity
    fk_errors = conn.execute("PRAGMA foreign_key_check;").fetchall()
    fk_status = "PASS" if len(fk_errors) == 0 else "FAIL"
    rows.append(
        ReconciliationCheckRow(
            metric_type="INTEGRITY",
            business_date="ALL",
            entity_id="DATABASE",
            metric_name="foreign_key_violations",
            expected_value="0",
            actual_value=str(len(fk_errors)),
            difference=str(len(fk_errors)),
            status=fk_status,
            explanation="All relational foreign keys are consistent." if fk_status == "PASS" else f"Violations: {fk_errors}",
        )
    )

    # 2. Rejection Traceability
    untraced = conn.execute(
        """
        SELECT COUNT(*) AS cnt
        FROM rejected_records r
        LEFT JOIN pipeline_runs p ON r.run_id = p.run_id
        WHERE p.run_id IS NULL;
        """
    ).fetchone()["cnt"]
    rej_status = "PASS" if untraced == 0 else "FAIL"
    rows.append(
        ReconciliationCheckRow(
            metric_type="INTEGRITY",
            business_date="ALL",
            entity_id="REJECTED_RECORDS",
            metric_name="untraceable_rejections",
            expected_value="0",
            actual_value=str(untraced),
            difference=str(untraced),
            status=rej_status,
            explanation="All quarantined records trace directly to an existing pipeline run.",
        )
    )

    # 3. Global Active Count Parity: Transactions vs Product Metrics vs Customer Metrics
    active_txn_cnt = conn.execute("SELECT COUNT(*) FROM transactions WHERE status = 'ACTIVE';").fetchone()[0]
    prod_agg_cnt = conn.execute("SELECT COALESCE(SUM(transaction_count), 0) FROM daily_product_metrics;").fetchone()[0]
    cust_agg_cnt = conn.execute("SELECT COALESCE(SUM(transaction_count), 0) FROM daily_customer_metrics;").fetchone()[0]

    cnt_status = "PASS" if active_txn_cnt == prod_agg_cnt == cust_agg_cnt else "FAIL"
    rows.append(
        ReconciliationCheckRow(
            metric_type="INTEGRITY",
            business_date="ALL",
            entity_id="GLOBAL_PARITY",
            metric_name="active_transaction_count_parity",
            expected_value=str(active_txn_cnt),
            actual_value=f"Prod:{prod_agg_cnt}, Cust:{cust_agg_cnt}",
            difference=str(abs(prod_agg_cnt - active_txn_cnt) + abs(cust_agg_cnt - active_txn_cnt)),
            status=cnt_status,
            explanation="Active transactions count matches sum of product metrics and sum of customer metrics.",
        )
    )

    # 4. Global Active Revenue Parity: Transactions vs Product Metrics vs Customer Metrics
    active_txn_rev = conn.execute("SELECT COALESCE(SUM(amount_minor), 0) FROM transactions WHERE status = 'ACTIVE';").fetchone()[0]
    prod_agg_rev = conn.execute("SELECT COALESCE(SUM(total_revenue_minor), 0) FROM daily_product_metrics;").fetchone()[0]
    cust_agg_rev = conn.execute("SELECT COALESCE(SUM(total_revenue_minor), 0) FROM daily_customer_metrics;").fetchone()[0]

    rev_status = "PASS" if active_txn_rev == prod_agg_rev == cust_agg_rev else "FAIL"
    rows.append(
        ReconciliationCheckRow(
            metric_type="INTEGRITY",
            business_date="ALL",
            entity_id="GLOBAL_PARITY",
            metric_name="active_revenue_parity_paise",
            expected_value=str(active_txn_rev),
            actual_value=f"Prod:{prod_agg_rev}, Cust:{cust_agg_rev}",
            difference=str(abs(prod_agg_rev - active_txn_rev) + abs(cust_agg_rev - active_txn_rev)),
            status=rev_status,
            explanation="Active transactions total revenue matches sum of product metrics and sum of customer metrics.",
        )
    )

    # 5. Pipeline Runs Accounting: Input Count == Accepted Count + Rejected Count
    runs_mismatch = conn.execute(
        """
        SELECT COUNT(*) FROM pipeline_runs
        WHERE status IN ('SUCCESS', 'PARTIAL') AND input_count != (accepted_count + rejected_count);
        """
    ).fetchone()[0]
    acc_status = "PASS" if runs_mismatch == 0 else "FAIL"
    rows.append(
        ReconciliationCheckRow(
            metric_type="INTEGRITY",
            business_date="ALL",
            entity_id="PIPELINE_RUNS",
            metric_name="run_accounting_integrity",
            expected_value="0",
            actual_value=str(runs_mismatch),
            difference=str(runs_mismatch),
            status=acc_status,
            explanation="All completed pipeline runs satisfy: input_count == accepted_count + rejected_count.",
        )
    )

    # 6. Quarantine Ledger Parity: Total rejections recorded in pipeline_runs matches rejected_records count
    total_run_rejections = conn.execute("SELECT COALESCE(SUM(rejected_count), 0) FROM pipeline_runs;").fetchone()[0]
    actual_rejections = conn.execute("SELECT COUNT(*) FROM rejected_records;").fetchone()[0]
    rej_match = "PASS" if total_run_rejections == actual_rejections else "FAIL"
    rows.append(
        ReconciliationCheckRow(
            metric_type="INTEGRITY",
            business_date="ALL",
            entity_id="REJECTED_RECORDS",
            metric_name="rejection_ledger_parity",
            expected_value=str(total_run_rejections),
            actual_value=str(actual_rejections),
            difference=str(abs(actual_rejections - total_run_rejections)),
            status=rej_match,
            explanation="Total pipeline_runs rejected_count matches physical rows in rejected_records table.",
        )
    )

    return rows


def perform_full_reconciliation(conn: sqlite3.Connection) -> list[ReconciliationCheckRow]:
    """Runs complete reconciliation suite."""
    rows = []
    rows.extend(run_product_metric_checks(conn))
    rows.extend(run_customer_metric_checks(conn))
    rows.extend(run_integrity_reconciliation(conn))
    return rows
