from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass(frozen=True)
class SweepStockSummary:
    sweep_id: UUID
    created_at: datetime
    facilities_checked_count: int
    facilities_with_stock_count: int

    @property
    def pct_in_stock(self) -> float:
        if self.facilities_checked_count == 0:
            return 1.0
        return self.facilities_with_stock_count / self.facilities_checked_count


@dataclass(frozen=True)
class FacilityCallStats:
    facility_id: UUID
    total_calls: int
    completed_calls: int

    @property
    def answer_rate(self) -> float:
        if self.total_calls == 0:
            return 0.0
        return self.completed_calls / self.total_calls
