from datetime import datetime
from typing import Protocol
from uuid import UUID

from app.domain.value_objects.analytics import FacilityCallStats, SweepStockSummary


class AnalyticsRepositoryPort(Protocol):
    async def list_sweep_stock_summaries(
        self,
        commodity_id: UUID,
        *,
        geography: str | None = None,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
    ) -> list[SweepStockSummary]: ...

    async def facility_call_stats(self, facility_id: UUID) -> FacilityCallStats: ...

    async def facility_result_confidences(self, facility_id: UUID) -> list[float]: ...

    async def list_facility_ids_with_calls(self) -> list[UUID]: ...
