"""
Affected period and aggregate group tracking.
Detects all (business_date, product_id) and (business_date, customer_id) combinations
that must be recomputed due to new events, updates, reversals, or attribute shifts.
"""

from dataclasses import dataclass, field


@dataclass
class AffectedPeriodsTracker:
    """Tracks unique affected product and customer reporting partitions."""

    product_groups: set[tuple[str, str]] = field(default_factory=set)  # (business_date, product_id)
    customer_groups: set[tuple[str, str]] = field(default_factory=set)  # (business_date, customer_id)

    def record_create(self, business_date: str, product_id: str, customer_id: str) -> None:
        """Records groups affected by a new transaction."""
        self.product_groups.add((business_date, product_id))
        self.customer_groups.add((business_date, customer_id))

    def record_update(
        self,
        old_date: str,
        old_product: str,
        old_customer: str,
        new_date: str,
        new_product: str,
        new_customer: str,
    ) -> None:
        """
        Records both old and new groups affected by an update.
        Ensures groups where transactions moved away are properly recomputed.
        """
        self.product_groups.add((old_date, old_product))
        self.product_groups.add((new_date, new_product))
        self.customer_groups.add((old_date, old_customer))
        self.customer_groups.add((new_date, new_customer))

    def record_reversal(self, business_date: str, product_id: str, customer_id: str) -> None:
        """Records groups affected by a reversed transaction."""
        self.product_groups.add((business_date, product_id))
        self.customer_groups.add((business_date, customer_id))

    def total_affected_count(self) -> int:
        """Total distinct aggregate partitions affected."""
        return len(self.product_groups) + len(self.customer_groups)

    def clear(self) -> None:
        """Resets tracked groups."""
        self.product_groups.clear()
        self.customer_groups.clear()
