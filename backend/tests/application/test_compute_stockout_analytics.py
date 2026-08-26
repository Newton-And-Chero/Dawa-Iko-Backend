"""ComputeStockoutAnalyticsUseCase — orchestration against in-memory fakes.
Bucketing/streak math itself is covered by tests/domain/test_stockout_analytics.py;
these tests cover the use case's own job: commodity lookup and the
human-readable summary line."""

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from app.application.use_cases.compute_stockout_analytics import ComputeStockoutAnalyticsUseCase
from app.core.exceptions import NotFoundError
from app.domain.entities.commodity import Commodity
from app.domain.enums import CommodityCategory
from app.domain.value_objects.analytics import SweepStockSummary
from tests.application.fakes import InMemoryAnalyticsRepository, InMemoryCommodityRepository


async def test_unknown_commodity_raises() -> None:
    use_case = ComputeStockoutAnalyticsUseCase(
        InMemoryAnalyticsRepository(), InMemoryCommodityRepository(), stockout_threshold_pct=0.5
    )
    with pytest.raises(NotFoundError):
        await use_case.execute(uuid4())


async def test_summary_counts_stockout_periods_in_recent_window() -> None:
    commodities = InMemoryCommodityRepository()
    commodity = await commodities.add(
        Commodity(name="Carbetocin", category=CommodityCategory.ESSENTIAL_MEDICINE)
    )
    analytics = InMemoryAnalyticsRepository()
    analytics.seed_summaries(
        commodity.id,
        "Kirinyaga",
        [
            SweepStockSummary(uuid4(), datetime(2026, 1, 5, tzinfo=UTC), 10, 0),
            SweepStockSummary(uuid4(), datetime(2026, 1, 12, tzinfo=UTC), 10, 10),
        ],
    )

    use_case = ComputeStockoutAnalyticsUseCase(analytics, commodities, stockout_threshold_pct=0.5)
    result = await use_case.execute(commodity.id, geography="Kirinyaga")

    assert len(result.buckets) == 2
    assert result.streak.current_streak == 0  # most recent week fully stocked
    assert result.streak.longest_streak == 1
    assert result.summary == "Carbetocin unavailable in Kirinyaga for 1 of the last 2 weeks"


async def test_no_sweep_history_yields_placeholder_summary() -> None:
    commodities = InMemoryCommodityRepository()
    commodity = await commodities.add(
        Commodity(name="Carbetocin", category=CommodityCategory.ESSENTIAL_MEDICINE)
    )
    use_case = ComputeStockoutAnalyticsUseCase(
        InMemoryAnalyticsRepository(), commodities, stockout_threshold_pct=0.5
    )

    result = await use_case.execute(commodity.id, geography="Kirinyaga")

    assert result.buckets == []
    assert result.summary == "no sweep history yet for Carbetocin in Kirinyaga"


async def test_missing_geography_falls_back_to_generic_wording_in_summary() -> None:
    commodities = InMemoryCommodityRepository()
    commodity = await commodities.add(
        Commodity(name="Carbetocin", category=CommodityCategory.ESSENTIAL_MEDICINE)
    )
    use_case = ComputeStockoutAnalyticsUseCase(
        InMemoryAnalyticsRepository(), commodities, stockout_threshold_pct=0.5
    )

    result = await use_case.execute(commodity.id)

    assert "the queried area" in result.summary
