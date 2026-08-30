from datetime import UTC, datetime
from uuid import uuid4

import pytest

from app.application.use_cases.request_manual_call import RequestManualCallUseCase
from app.core.config import Settings
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
    FakeCallGate,
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
        "call_gate": FakeCallGate(),
    }


def _use_case(setup: dict) -> RequestManualCallUseCase:
    return RequestManualCallUseCase(
        call_repository=setup["calls"],
        facility_repository=setup["facilities"],
        sweep_repository=setup["sweeps"],
        commodity_repository=setup["commodities"],
        call_provider=setup["call_provider"],
        call_gate=setup["call_gate"],
        realtime_event_bus=InMemoryRealtimeEventBus(),
        settings=setup.get("settings", Settings()),
    )


async def test_bypasses_cooldown_for_a_recently_called_facility(setup: dict) -> None:
    facility = await setup["facilities"].add(_facility())
    commodity = await setup["commodities"].add(
        Commodity(name="Carbetocin", category=CommodityCategory.ESSENTIAL_MEDICINE)
    )
    await setup["calls"].add(
        Call(
            sweep_id=facility.id,
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


async def test_disabled_call_engine_completes_the_sweep_without_calling(setup: dict) -> None:
    setup["call_gate"] = FakeCallGate(enabled=False)
    facility = await setup["facilities"].add(_facility())
    commodity = await setup["commodities"].add(
        Commodity(name="Carbetocin", category=CommodityCategory.ESSENTIAL_MEDICINE)
    )

    sweep_id = await _use_case(setup).execute(facility_id=facility.id, commodity_id=commodity.id)

    sweep = await setup["sweeps"].get_by_id(sweep_id)
    assert sweep is not None
    assert sweep.status == SweepStatus.COMPLETED
    assert await setup["calls"].list_by_sweep_id(sweep_id) == []
    assert len(setup["call_provider"].calls) == 0


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
