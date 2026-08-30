from datetime import UTC, datetime
from uuid import uuid4

from app.application.use_cases.compute_watchlist_trends import ComputeWatchlistTrendsUseCase
from app.domain.entities.commodity import Commodity
from app.domain.enums import CommodityCategory
from app.domain.value_objects.analytics import SweepStockSummary
from tests.application.fakes import InMemoryAnalyticsRepository, InMemoryCommodityRepository


async def test_ranks_commodities_by_average_stockout_rate_and_excludes_non_watchlist() -> None:
    commodities = InMemoryCommodityRepository()
    carbetocin = await commodities.add(
        Commodity(
            name="Carbetocin",
            category=CommodityCategory.ESSENTIAL_MEDICINE,
            is_priority_watchlist=True,
        )
    )
    insulin = await commodities.add(
        Commodity(
            name="Insulin",
            category=CommodityCategory.ESSENTIAL_MEDICINE,
            is_priority_watchlist=True,
        )
    )
    non_watchlist = await commodities.add(
        Commodity(
            name="Paracetamol",
            category=CommodityCategory.ESSENTIAL_MEDICINE,
            is_priority_watchlist=False,
        )
    )

    analytics = InMemoryAnalyticsRepository()
    when = datetime(2026, 1, 5, tzinfo=UTC)
    analytics.seed_summaries(carbetocin.id, "Kirinyaga", [SweepStockSummary(uuid4(), when, 10, 0)])
    analytics.seed_summaries(carbetocin.id, "Nairobi", [SweepStockSummary(uuid4(), when, 10, 0)])
    analytics.seed_summaries(insulin.id, "Kirinyaga", [SweepStockSummary(uuid4(), when, 10, 10)])
    analytics.seed_summaries(insulin.id, "Nairobi", [SweepStockSummary(uuid4(), when, 10, 5)])
    analytics.seed_summaries(
        non_watchlist.id, "Kirinyaga", [SweepStockSummary(uuid4(), when, 10, 0)]
    )

    use_case = ComputeWatchlistTrendsUseCase(analytics, commodities, stockout_threshold_pct=0.5)
    result = await use_case.execute(["Kirinyaga", "Nairobi"])

    assert len(result.rows) == 4
    assert result.ranked_commodity_ids == [carbetocin.id, insulin.id]
    assert non_watchlist.id not in result.ranked_commodity_ids


async def test_commodity_with_no_sweep_history_in_any_county_is_unranked() -> None:
    commodities = InMemoryCommodityRepository()
    commodity = await commodities.add(
        Commodity(
            name="Carbetocin",
            category=CommodityCategory.ESSENTIAL_MEDICINE,
            is_priority_watchlist=True,
        )
    )

    use_case = ComputeWatchlistTrendsUseCase(
        InMemoryAnalyticsRepository(), commodities, stockout_threshold_pct=0.5
    )
    result = await use_case.execute(["Kirinyaga"])

    assert len(result.rows) == 1
    assert result.rows[0].sweep_count == 0
    assert result.rows[0].stockout_rate == 0.0
    assert result.ranked_commodity_ids == []
    assert commodity.id not in result.ranked_commodity_ids
