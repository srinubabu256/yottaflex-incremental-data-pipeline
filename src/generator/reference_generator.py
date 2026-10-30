"""
Synthetic Reference Data Generator for Products and Customers.
Produces reproducible reference CSVs for the YottaFlex pipeline.
"""

import csv
import random
from pathlib import Path
from datetime import datetime, timezone

CATEGORIES = [
    "Electronics",
    "Apparel",
    "Home & Kitchen",
    "Books & Media",
    "Health & Personal Care",
    "Sports & Outdoors",
    "Industrial & Scientific",
    "Grocery & Gourmet",
]

PRODUCT_ADJECTIVES = ["Pro", "Max", "Ultra", "Flex", "Prime", "Lite", "Nova", "Elite", "Core", "Apex"]
PRODUCT_NOUNS = [
    "Hub", "Router", "Display", "Sensor", "Controller", "Module", "Adapter", "Terminal",
    "Drive", "Engine", "Beacon", "Transmitter", "Receiver", "Scanner", "Matrix", "Bridge"
]

FIRST_NAMES = [
    "Aarav", "Aditi", "Rohan", "Priya", "Vikram", "Neha", "Rahul", "Ananya", "Siddharth", "Pooja",
    "Karan", "Tanvi", "Arjun", "Kavya", "Varun", "Riya", "Aditya", "Ishaan", "Meera", "Sameer"
]

LAST_NAMES = [
    "Sharma", "Verma", "Patel", "Reddy", "Nair", "Iyer", "Mehta", "Singh", "Kumar", "Chopra",
    "Gupta", "Rao", "Deshmukh", "Joshi", "Bose", "Chatterjee", "Menon", "Pillai", "Nambiar", "Das"
]


def generate_reference_products(count: int = 50, seed: int = 42) -> list[dict[str, str]]:
    """Generates a reproducible list of synthetic products."""
    rng = random.Random(seed)
    products = []
    base_time = "2026-01-01T00:00:00Z"

    for i in range(1, count + 1):
        prod_id = f"PRD-{i:04d}"
        adj = rng.choice(PRODUCT_ADJECTIVES)
        noun = rng.choice(PRODUCT_NOUNS)
        name = f"Yotta {adj} {noun} {rng.randint(100, 999)}"
        category = rng.choice(CATEGORIES)
        products.append({
            "product_id": prod_id,
            "product_name": name,
            "category": category,
            "created_at": base_time,
            "updated_at": "",
        })
    return products


def generate_reference_customers(count: int = 100, seed: int = 42) -> list[dict[str, str]]:
    """Generates a reproducible list of synthetic customers."""
    rng = random.Random(seed)
    customers = []
    base_time = "2026-01-01T00:00:00Z"

    for i in range(1, count + 1):
        cust_id = f"CUST-{i:04d}"
        first = rng.choice(FIRST_NAMES)
        last = rng.choice(LAST_NAMES)
        full_name = f"{first} {last}"
        email = f"{first.lower()}.{last.lower()}{rng.randint(10, 99)}@example.com"
        customers.append({
            "customer_id": cust_id,
            "customer_name": full_name,
            "email": email,
            "created_at": base_time,
            "updated_at": "",
        })
    return customers


def save_reference_data(
    output_dir: Path,
    product_count: int = 50,
    customer_count: int = 100,
    seed: int = 42,
) -> tuple[Path, Path]:
    """Generates and writes products.csv and customers.csv."""
    output_dir.mkdir(parents=True, exist_ok=True)
    prod_path = output_dir / "products.csv"
    cust_path = output_dir / "customers.csv"

    products = generate_reference_products(product_count, seed)
    customers = generate_reference_customers(customer_count, seed)

    with open(prod_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["product_id", "product_name", "category", "created_at", "updated_at"])
        writer.writeheader()
        writer.writerows(products)

    with open(cust_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["customer_id", "customer_name", "email", "created_at", "updated_at"])
        writer.writeheader()
        writer.writerows(customers)

    return prod_path, cust_path
