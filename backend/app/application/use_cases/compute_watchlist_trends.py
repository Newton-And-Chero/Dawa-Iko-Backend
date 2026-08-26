"""Cross-commodity, cross-county comparison across the priority watchlist —
PROJECT.md 2.8's "which essential medicines are most chronically
unavailable, county comparison." Counties are caller-supplied: there is no
cheap way to discover "every county a sweep has ever covered" from the
JSONB `geography_scope` without scanning every sweep, and the caller (an
analyst picking counties to compare, or a scheduled report) already knows
which ones it cares about.

Deferred (PROJECT.md §5, workflows/08 "Explicitly deferred"): correlating
these rates against published KEMSA fill-rate data, and a ward-level
chronic-stockout heatmap, would both plug in here as additional dimensions
alongside `county` — not built in this sprint.
"""

from dataclasses import dataclass
from uuid import UUID

from app.application.ports.analytics_repository_port import AnalyticsRepositoryPort
from app.application.ports.commodity_repository import CommodityRepositoryPort
from app.application.use_cases.list_commodities import CommodityFilter


@dataclass(frozen=True)
class WatchlistTrendRow:
    commodity_id: UUID
    commodity_name: str
    county: str
    sweep_count: int
    stockout_sweep_count: int

    @property
    def stockout_rate(self) -> float:
        if self.sweep_count == 0:
            return 0.0
        return self.stockout_sweep_count / self.sweep_count


@dataclass(frozen=True)
class WatchlistTrendsResult:
    rows: list[WatchlistTrendRow]
    # Commodity ids ordered most-chronically-unavailable first (by mean
    # stockout rate across the counties that have any sweep history).
    ranked_commodity_ids: list[UUID]


class ComputeWatchlistTrendsUseCase:
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

    async def execute(self, counties: list[str]) -> WatchlistTrendsResult:
        commodities = await self._commodities.list_by_filter(
            CommodityFilter(is_priority_watchlist=True)
        )

        rows: list[WatchlistTrendRow] = []
        rates_by_commodity: dict[UUID, list[float]] = {}
        for commodity in commodities:
            for county in counties:
                summaries = await self._analytics.list_sweep_stock_summaries(
                    commodity.id, geography=county
                )
                stockout_count = sum(1 for s in summaries if s.pct_in_stock <= self._threshold)
                rows.append(
                    WatchlistTrendRow(
                        commodity_id=commodity.id,
                        commodity_name=commodity.name,
                        county=county,
                        sweep_count=len(summaries),
                        stockout_sweep_count=stockout_count,
                    )
                )
                if summaries:
                    rates_by_commodity.setdefault(commodity.id, []).append(
                        stockout_count / len(summaries)
                    )

        ranked = sorted(
            rates_by_commodity,
            key=lambda cid: sum(rates_by_commodity[cid]) / len(rates_by_commodity[cid]),
            reverse=True,
        )
        return WatchlistTrendsResult(rows=rows, ranked_commodity_ids=ranked)
