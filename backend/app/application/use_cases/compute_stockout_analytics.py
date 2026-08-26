"""Stockout rate/duration analytics for a commodity+geography — PROJECT.md
2.7/2.8's "carbetocin unavailable in this ward for 6 of the last 8 weeks"
framing. Read/derive only (workflows/08): never writes Sweep/Call/
AvailabilityResult data."""

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from app.application.ports.analytics_repository_port import AnalyticsRepositoryPort
from app.application.ports.commodity_repository import CommodityRepositoryPort
from app.core.exceptions import NotFoundError
from app.domain.services.stockout_analytics import (
    BucketGranularity,
    StockoutRateBucket,
    StockoutStreak,
    bucket_stockout_rate,
    compute_stockout_streak,
)

# How many of the most recent buckets the human-readable `summary` line
# covers, e.g. "...for 6 of the last 8 weeks" — matches PROJECT.md's own
# example window.
_SUMMARY_WINDOW = 8


@dataclass(frozen=True)
class StockoutAnalyticsResult:
    commodity_id: UUID
    commodity_name: str
    geography: str | None
    granularity: BucketGranularity
    buckets: list[StockoutRateBucket]
    streak: StockoutStreak
    summary: str


class ComputeStockoutAnalyticsUseCase:
    def __init__(
        self,
        analytics_repository: AnalyticsRepositoryPort,
        commodity_repository: CommodityRepositoryPort,
        *,
        stockout_threshold_pct: float,
    ) -> None:
        self._analytics = analytics_repository
        self._commodities = commodity_repository
        self._threshold = stockout_threshold_pct

    async def execute(
        self,
        commodity_id: UUID,
        *,
        geography: str | None = None,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
        granularity: BucketGranularity = "week",
    ) -> StockoutAnalyticsResult:
        commodity = await self._commodities.get_by_id(commodity_id)
        if commodity is None:
            raise NotFoundError(f"commodity {commodity_id} not found")

        summaries = await self._analytics.list_sweep_stock_summaries(
            commodity_id, geography=geography, date_from=date_from, date_to=date_to
        )
        buckets = bucket_stockout_rate(
            summaries, threshold_pct=self._threshold, granularity=granularity
        )
        streak = compute_stockout_streak(summaries, threshold_pct=self._threshold)

        location = geography or "the queried area"
        recent = buckets[-_SUMMARY_WINDOW:]
        if recent:
            stockout_periods = sum(1 for b in recent if b.stockout_rate > 0)
            summary = (
                f"{commodity.name} unavailable in {location} for {stockout_periods} of the "
                f"last {len(recent)} {granularity}s"
            )
        else:
            summary = f"no sweep history yet for {commodity.name} in {location}"

        return StockoutAnalyticsResult(
            commodity_id=commodity_id,
            commodity_name=commodity.name,
            geography=geography,
            granularity=granularity,
            buckets=buckets,
            streak=streak,
            summary=summary,
        )
