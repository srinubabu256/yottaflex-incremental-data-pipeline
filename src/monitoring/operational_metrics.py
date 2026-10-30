"""
Operational metrics and throughput calculations.
"""

from dataclasses import dataclass


@dataclass
class OperationalSummary:
    run_id: str
    duration_seconds: float
    total_records: int
    records_per_second: float
    accepted_records: int
    rejected_records: int
    acceptance_rate_pct: float

    @classmethod
    def calculate(
        cls,
        run_id: str,
        duration_seconds: float,
        total_records: int,
        accepted_records: int,
        rejected_records: int,
    ) -> "OperationalSummary":
        rps = (total_records / duration_seconds) if duration_seconds > 0 else 0.0
        pct = (accepted_records / total_records * 100.0) if total_records > 0 else 100.0
        return cls(
            run_id=run_id,
            duration_seconds=round(duration_seconds, 4),
            total_records=total_records,
            records_per_second=round(rps, 2),
            accepted_records=accepted_records,
            rejected_records=rejected_records,
            acceptance_rate_pct=round(pct, 2),
        )
