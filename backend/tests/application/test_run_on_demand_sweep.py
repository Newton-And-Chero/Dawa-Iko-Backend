"""RunOnDemandSweepUseCase dispatch orchestration — resolution is stubbed out
(FakeGeographyResolver) since that's PostGISGeographyResolver's job (covered
in tests/infrastructure/test_geography_resolver.py); these tests assert on
chunking, cooldown exclusion, and the Sweep/Call rows the use case creates.
"""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from app.application.use_cases.run_on_demand_sweep import RunOnDemandSweepUseCase
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
from app.domain.value_objects.geography_scope import CountyScope
from tests.application.fakes import (
    FakeCallProvider,
    FakeGeographyResolver,
    InMemoryCallRepository,
    InMemoryCommodityRepository,
    InMemoryRealtimeEventBus,
    InMemorySweepRepository,
)


def _facility(n: int) -> Facility:
    return Facility(
        name=f"Facility {n}",
        type=FacilityType.DISPENSARY,
        county="Kirinyaga",
        sub_county="Mwea",
        ward="Wamumu",
        gps_lat=-0.6849,
        gps_lng=37.3667,
        phone_number=f"+2547000{n:05d}",
        source=FacilitySource.KMHFL,
    )


@pytest.fixture
def setup() -> dict:
    commodities = InMemoryCommodityRepository()
    calls = InMemoryCallRepository()
    sweeps = InMemorySweepRepository()
    call_provider = FakeCallProvider()
    return {
        "commodities": commodities,
        "calls": calls,
        "sweeps": sweeps,
        "call_provider": call_provider,
    }


def _use_case(
    setup: dict, facilities: list[Facility], settings: Settings
) -> RunOnDemandSweepUseCase:
    return RunOnDemandSweepUseCase(
        geography_resolver=FakeGeographyResolver(facilities),
        call_repository=setup["calls"],
        sweep_repository=setup["sweeps"],
        commodity_repository=setup["commodities"],
        call_provider=setup["call_provider"],
        settings=settings,
        realtime_event_bus=InMemoryRealtimeEventBus(),
    )


async def test_unknown_commodity_raises(setup: dict) -> None:
    use_case = _use_case(setup, [], Settings())
    with pytest.raises(NotFoundError):
        await use_case.execute(commodity_id=uuid4(), geography=CountyScope(county="Kirinyaga"))


async def test_dispatch_creates_sweep_and_call_rows(setup: dict) -> None:
    commodity = await setup["commodities"].add(
        Commodity(name="Carbetocin", category=CommodityCategory.ESSENTIAL_MEDICINE)
    )
    facilities = [_facility(i) for i in range(3)]
    use_case = _use_case(setup, facilities, Settings(MAX_RECIPIENTS_PER_TASK=50))

    sweep_id = await use_case.execute(
        commodity_id=commodity.id, geography=CountyScope(county="Kirinyaga")
    )

    sweep = await setup["sweeps"].get_by_id(sweep_id)
    assert sweep is not None
    assert sweep.status == SweepStatus.IN_PROGRESS

    calls = await setup["calls"].list_by_sweep_id(sweep_id)
    assert len(calls) == 3
    assert all(c.status == CallStatus.QUEUED for c in calls)
    assert all(c.provider_call_id is not None for c in calls)


async def test_chunking_produces_multiple_place_call_invocations_with_distinct_keys(
    setup: dict,
) -> None:
    commodity = await setup["commodities"].add(
        Commodity(name="Carbetocin", category=CommodityCategory.ESSENTIAL_MEDICINE)
    )
    facilities = [_facility(i) for i in range(5)]
    use_case = _use_case(setup, facilities, Settings(MAX_RECIPIENTS_PER_TASK=2))

    sweep_id = await use_case.execute(
        commodity_id=commodity.id, geography=CountyScope(county="Kirinyaga")
    )

    provider_calls = setup["call_provider"].calls
    assert len(provider_calls) == 3  # chunks of 2, 2, 1
    idempotency_keys = [c["idempotency_key"] for c in provider_calls]
    assert len(set(idempotency_keys)) == 3
    assert all(key.startswith(f"{sweep_id}:") for key in idempotency_keys)

    calls = await setup["calls"].list_by_sweep_id(sweep_id)
    assert len(calls) == 5
    assert all(c.sweep_id == sweep_id for c in calls)


async def test_facility_within_cooldown_window_is_excluded(setup: dict) -> None:
    commodity = await setup["commodities"].add(
        Commodity(name="Carbetocin", category=CommodityCategory.ESSENTIAL_MEDICINE)
    )
    facilities = [_facility(0), _facility(1)]

    recently_called = Call(
        sweep_id=uuid4(),
        facility_id=facilities[0].id,
        status=CallStatus.COMPLETED,
        started_at=datetime.now(UTC) - timedelta(hours=1),
    )
    await setup["calls"].add(recently_called)

    use_case = _use_case(
        setup, facilities, Settings(MAX_RECIPIENTS_PER_TASK=50, FACILITY_CALL_COOLDOWN_HOURS=24)
    )
    sweep_id = await use_case.execute(
        commodity_id=commodity.id, geography=CountyScope(county="Kirinyaga")
    )

    calls = await setup["calls"].list_by_sweep_id(sweep_id)
    assert {c.facility_id for c in calls} == {facilities[1].id}


async def test_demo_redirect_numbers_cap_the_chunk_and_reroute_every_call(setup: dict) -> None:
    commodity = await setup["commodities"].add(
        Commodity(name="Carbetocin", category=CommodityCategory.ESSENTIAL_MEDICINE)
    )
    facilities = [_facility(i) for i in range(5)]
    use_case = _use_case(
        setup,
        facilities,
        Settings(
            MAX_RECIPIENTS_PER_TASK=50,
            CALL_DEMO_REDIRECT_NUMBERS=["+254792036343", "+254720168641"],
        ),
    )

    sweep_id = await use_case.execute(
        commodity_id=commodity.id, geography=CountyScope(county="Kirinyaga")
    )

    calls = await setup["calls"].list_by_sweep_id(sweep_id)
    assert len(calls) == 2  # capped to the number of demo numbers
    assert all(c.provider_recipient_id is not None for c in calls)

    provider_calls = setup["call_provider"].calls
    assert len(provider_calls) == 1
    dialed = {r.phones[0] for r in provider_calls[0]["recipients"]}
    assert dialed == {"+254792036343", "+254720168641"}


async def test_running_twice_in_succession_does_not_recall_cooling_down_facility(
    setup: dict,
) -> None:
    commodity = await setup["commodities"].add(
        Commodity(name="Carbetocin", category=CommodityCategory.ESSENTIAL_MEDICINE)
    )
    facilities = [_facility(0)]
    use_case = _use_case(
        setup, facilities, Settings(MAX_RECIPIENTS_PER_TASK=50, FACILITY_CALL_COOLDOWN_HOURS=24)
    )

    first_sweep_id = await use_case.execute(
        commodity_id=commodity.id, geography=CountyScope(county="Kirinyaga")
    )
    first_calls = await setup["calls"].list_by_sweep_id(first_sweep_id)
    assert len(first_calls) == 1

    second_sweep_id = await use_case.execute(
        commodity_id=commodity.id, geography=CountyScope(county="Kirinyaga")
    )
    second_calls = await setup["calls"].list_by_sweep_id(second_sweep_id)
    assert len(second_calls) == 0

    second_sweep = await setup["sweeps"].get_by_id(second_sweep_id)
    assert second_sweep is not None
    assert second_sweep.status == SweepStatus.COMPLETED
