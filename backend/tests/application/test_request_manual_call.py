"""RequestManualCallUseCase — the one documented cooldown bypass: a facility
called moments ago is still callable manually."""

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from app.application.use_cases.request_manual_call import RequestManualCallUseCase
from app.core.exceptions import NotFoundError
from app.domain.entities.call import Call
from app.domain.entities.commodity import Commodity
from app.domain.entities.facility import Facility
from app.domain.enums import (
    CallStatus,
    CommodityCategory,
    FacilitySource,
    FacilityType,
    SweepStatus,
)
from tests.application.fakes import (
    FakeCallProvider,
    InMemoryCallRepository,
    InMemoryCommodityRepository,
    InMemoryFacilityRepository,
    InMemoryRealtimeEventBus,
    InMemorySweepRepository,
)


def _facility() -> Facility:
    return Facility(
        name="Test Dispensary",
        type=FacilityType.DISPENSARY,
        county="Kirinyaga",
        sub_county="Mwea",
        ward="Wamumu",
        gps_lat=-0.6849,
        gps_lng=37.3667,
        phone_number="+254700000001",
        source=FacilitySource.KMHFL,
    )


@pytest.fixture
def setup() -> dict:
    return {
        "calls": InMemoryCallRepository(),
        "facilities": InMemoryFacilityRepository(),
        "sweeps": InMemorySweepRepository(),
        "commodities": InMemoryCommodityRepository(),
        "call_provider": FakeCallProvider(),
    }


def _use_case(setup: dict) -> RequestManualCallUseCase:
    return RequestManualCallUseCase(
        call_repository=setup["calls"],
        facility_repository=setup["facilities"],
        sweep_repository=setup["sweeps"],
        commodity_repository=setup["commodities"],
        call_provider=setup["call_provider"],
        realtime_event_bus=InMemoryRealtimeEventBus(),
    )


async def test_bypasses_cooldown_for_a_recently_called_facility(setup: dict) -> None:
    facility = await setup["facilities"].add(_facility())
    commodity = await setup["commodities"].add(
        Commodity(name="Carbetocin", category=CommodityCategory.ESSENTIAL_MEDICINE)
    )
    # Facility was just called a minute ago — would be cooldown-blocked in a sweep.
    await setup["calls"].add(
        Call(
            sweep_id=facility.id,  # arbitrary unrelated sweep id for this fake
            facility_id=facility.id,
            status=CallStatus.COMPLETED,
            started_at=datetime.now(UTC),
        )
    )

    sweep_id = await _use_case(setup).execute(facility_id=facility.id, commodity_id=commodity.id)

    sweep = await setup["sweeps"].get_by_id(sweep_id)
    assert sweep is not None
    assert sweep.status == SweepStatus.IN_PROGRESS

    calls = await setup["calls"].list_by_sweep_id(sweep_id)
    assert len(calls) == 1
    assert calls[0].facility_id == facility.id
    assert len(setup["call_provider"].calls) == 1


async def test_unknown_facility_raises(setup: dict) -> None:
    commodity = await setup["commodities"].add(
        Commodity(name="Carbetocin", category=CommodityCategory.ESSENTIAL_MEDICINE)
    )
    with pytest.raises(NotFoundError):
        await _use_case(setup).execute(facility_id=uuid4(), commodity_id=commodity.id)


async def test_unknown_commodity_raises(setup: dict) -> None:
    facility = await setup["facilities"].add(_facility())
    with pytest.raises(NotFoundError):
        await _use_case(setup).execute(facility_id=facility.id, commodity_id=uuid4())
