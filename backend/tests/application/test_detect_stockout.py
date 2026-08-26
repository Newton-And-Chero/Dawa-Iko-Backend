"""DetectStockoutUseCase — threshold/severity wiring against in-memory fakes.
`domain/services/severity.py` already covers the classification matrix
(tests/domain/test_severity.py); these tests cover the use case's own job:
counting calls/results for a sweep and deciding whether to call it at all.
"""

from uuid import uuid4

import pytest

from app.application.use_cases.detect_stockout import DetectStockoutUseCase
from app.core.config import Settings
from app.core.exceptions import NotFoundError
from app.domain.entities.availability_result import AvailabilityResult
from app.domain.entities.call import Call
from app.domain.entities.commodity import Commodity
from app.domain.entities.sweep import Sweep
from app.domain.enums import CommodityCategory, StockStatus, SweepTrigger
from tests.application.fakes import (
    InMemoryAvailabilityResultRepository,
    InMemoryCallRepository,
    InMemoryCommodityRepository,
    InMemoryRealtimeEventBus,
    InMemoryStockoutAlertRepository,
    InMemorySweepRepository,
)


@pytest.fixture
def setup() -> dict:
    return {
        "sweeps": InMemorySweepRepository(),
        "calls": InMemoryCallRepository(),
        "results": InMemoryAvailabilityResultRepository(),
        "commodities": InMemoryCommodityRepository(),
        "alerts": InMemoryStockoutAlertRepository(),
        "bus": InMemoryRealtimeEventBus(),
    }


def _use_case(setup: dict, settings: Settings | None = None) -> DetectStockoutUseCase:
    return DetectStockoutUseCase(
        sweep_repository=setup["sweeps"],
        call_repository=setup["calls"],
        availability_result_repository=setup["results"],
        commodity_repository=setup["commodities"],
        stockout_alert_repository=setup["alerts"],
        realtime_event_bus=setup["bus"],
        settings=settings or Settings(),
    )


async def _seed_sweep(setup: dict, *, is_priority_watchlist: bool = False) -> Sweep:
    commodity = await setup["commodities"].add(
        Commodity(
            name="Carbetocin",
            category=CommodityCategory.ESSENTIAL_MEDICINE,
            is_priority_watchlist=is_priority_watchlist,
        )
    )
    sweep = Sweep(
        commodity_id=commodity.id,
        geography_scope={"kind": "county", "county": "Kirinyaga"},
        trigger_type=SweepTrigger.ON_DEMAND,
    )
    return await setup["sweeps"].add(sweep)


async def _seed_call_with_result(setup: dict, sweep_id, in_stock: StockStatus) -> None:
    call = await setup["calls"].add(Call(sweep_id=sweep_id, facility_id=uuid4()))
    await setup["results"].add(
        AvailabilityResult(
            call_id=call.id, facility_id=call.facility_id, commodity_id=uuid4(), in_stock=in_stock
        )
    )


async def test_unknown_sweep_raises(setup: dict) -> None:
    with pytest.raises(NotFoundError):
        await _use_case(setup).execute(uuid4())


async def test_zero_calls_creates_no_alert(setup: dict) -> None:
    sweep = await _seed_sweep(setup)
    alert = await _use_case(setup).execute(sweep.id)
    assert alert is None
    assert await setup["alerts"].list_all() == []


async def test_full_stock_creates_no_alert(setup: dict) -> None:
    sweep = await _seed_sweep(setup)
    for _ in range(4):
        await _seed_call_with_result(setup, sweep.id, StockStatus.YES)

    alert = await _use_case(setup).execute(sweep.id)
    assert alert is None


async def test_zero_stock_creates_an_alert_and_publishes_it(setup: dict) -> None:
    sweep = await _seed_sweep(setup, is_priority_watchlist=True)
    for _ in range(3):
        await _seed_call_with_result(setup, sweep.id, StockStatus.NO)

    alert = await _use_case(setup).execute(sweep.id)

    assert alert is not None
    assert alert.commodity_id == sweep.commodity_id
    assert alert.geography == sweep.geography_scope
    assert alert.facilities_checked_count == 3
    assert alert.facilities_with_stock_count == 0
    assert await setup["alerts"].get_by_id(alert.id) is not None

    published_types = [event["type"] for _, event in setup["bus"].published]
    assert "alert.created" in published_types


async def test_below_threshold_but_above_scarcity_still_creates_an_alert(setup: dict) -> None:
    """3/10 in stock: below the 0.5 threshold gate, and severity.py itself
    still finds it scarce enough (see test_severity.py's own matrix)."""
    sweep = await _seed_sweep(setup)
    for _ in range(3):
        await _seed_call_with_result(setup, sweep.id, StockStatus.YES)
    for _ in range(7):
        await _seed_call_with_result(setup, sweep.id, StockStatus.NO)

    alert = await _use_case(setup).execute(sweep.id)

    assert alert is not None
    assert alert.facilities_with_stock_count == 3
    assert alert.facilities_checked_count == 10
