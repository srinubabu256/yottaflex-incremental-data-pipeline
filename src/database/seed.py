"""
Seed reference data (products and customers) into the database.
"""

import csv
from pathlib import Path
from src.database.connection import DatabaseConnection, get_db
from src.config.settings import get_settings
from src.config.logging_config import get_logger

logger = get_logger(__name__)


def seed_reference_data(
    db: DatabaseConnection | None = None,
    products_csv: Path | None = None,
    customers_csv: Path | None = None,
) -> tuple[int, int]:
    """
    Seeds products and customers from reference CSV files.
    Returns (products_seeded_count, customers_seeded_count).
    """
    db = db or get_db()
    settings = get_settings()

    prod_file = products_csv or (settings.reference_data_dir / "products.csv")
    cust_file = customers_csv or (settings.reference_data_dir / "customers.csv")

    if not prod_file.exists():
        raise FileNotFoundError(f"Products reference file not found at: {prod_file}")
    if not cust_file.exists():
        raise FileNotFoundError(f"Customers reference file not found at: {cust_file}")

    products_count = 0
    customers_count = 0

    with db.transaction() as conn:
        # Load products
        with open(prod_file, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            prod_rows = list(reader)
            for row in prod_rows:
                conn.execute(
                    """
                    INSERT INTO products (product_id, product_name, category, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?)
                    ON CONFLICT(product_id) DO UPDATE SET
                        product_name = excluded.product_name,
                        category = excluded.category,
                        updated_at = excluded.updated_at;
                    """,
                    (
                        row["product_id"].strip(),
                        row["product_name"].strip(),
                        row.get("category", "").strip() or None,
                        row.get("created_at", "").strip(),
                        row.get("updated_at", "").strip() or None,
                    ),
                )
                products_count += 1

        # Load customers
        with open(cust_file, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            cust_rows = list(reader)
            for row in cust_rows:
                conn.execute(
                    """
                    INSERT INTO customers (customer_id, customer_name, email, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?)
                    ON CONFLICT(customer_id) DO UPDATE SET
                        customer_name = excluded.customer_name,
                        email = excluded.email,
                        updated_at = excluded.updated_at;
                    """,
                    (
                        row["customer_id"].strip(),
                        row["customer_name"].strip(),
                        row.get("email", "").strip() or None,
                        row.get("created_at", "").strip(),
                        row.get("updated_at", "").strip() or None,
                    ),
                )
                customers_count += 1

    logger.info(f"Seeded {products_count} products and {customers_count} customers.")
    return products_count, customers_count
