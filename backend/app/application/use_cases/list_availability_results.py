"""List/filter/rank availability results — the endpoint a "where can I get
X" view is built from (PROJECT.md 2.7's query view spec): in-stock results
first, most confident first, per commodity/geography/date-range/stock-status.
"""

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from app.application.ports.availability_result_repository import (
    AvailabilityResultRepositoryPort,
)
from app.domain.entities.availability_result import AvailabilityResult
from app.domain.enums import StockStatus


@dataclass
class AvailabilityResultFilter:
    commodity_id: UUID | None = None
    # Facility.county exact match — availability results don't carry
    # geography themselves, so filtering by it is a join at the repository.
    county: str | None = None
    date_from: datetime | None = None
    date_to: datetime | None = None
    in_stock: StockStatus | None = None


def _rank_key(result: AvailabilityResult) -> tuple[int, float, float]:
    in_stock_first = 0 if result.in_stock == StockStatus.YES else 1
    confidence = -(result.confidence or 0.0)
    return (in_stock_first, confidence, -result.created_at.timestamp())


class ListAvailabilityResultsUseCase:
    def __init__(self, availability_result_repository: AvailabilityResultRepositoryPort) -> None:
        self._results = availability_result_repository

    async def execute(
        self, result_filter: AvailabilityResultFilter | None = None
    ) -> list[AvailabilityResult]:
        results = await self._results.list_by_filter(result_filter or AvailabilityResultFilter())
        return sorted(results, key=_rank_key)
