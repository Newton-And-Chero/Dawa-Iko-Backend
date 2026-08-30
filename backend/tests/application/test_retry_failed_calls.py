from datetime import UTC, datetime, timedelta

import pytest

from app.application.use_cases.retry_failed_calls import RetryFailedCallsUseCase
from app.core.config import Settings
from app.domain.entities.call import Call
from app.domain.entities.commodity import Commodity
from app.domain.entities.facility import Facility
from app.domain.entities.sweep import Sweep
from app.domain.enums import (
    CallStatus,
    CommodityCategory,
    FacilitySource,
    FacilityType,
    SweepStatus,
    SweepTrigger,
)
from app.domain.value_objects.geography_scope import CountyScope, geography_scope_to_dict
from tests.application.fakes import (
    FakeCallGate,
    FakeCallProvider,
    InMemoryCallRepository,
    InMemoryCommodityRepository,
    InMemoryFacilityRepository,
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


async def _seed(setup: dict, *, attempt_number: int, ended_at: datetime) -> Call:
    facility = await setup["facilities"].add(_facility())
    commodity = await setup["commodities"].add(
        Commodity(name="Carbetocin", category=CommodityCategory.ESSENTIAL_MEDICINE)
    )
    sweep = await setup["sweeps"].add(
        Sweep(
            commodity_id=commodity.id,
            geography_scope=geography_scope_to_dict(CountyScope(county="Kirinyaga")),
            trigger_type=SweepTrigger.ON_DEMAND,
            status=SweepStatus.COMPLETED,
        )
    )
    call = Call(
        sweep_id=sweep.id,
        facility_id=facility.id,
        status=CallStatus.NO_ANSWER,
        attempt_number=attempt_number,
        ended_at=ended_at,
    )
    await setup["calls"].add(call)
    return call


def _use_case(setup: dict) -> RetryFailedCallsUseCase:
    return RetryFailedCallsUseCase(
        call_repository=setup["calls"],
        facility_repository=setup["facilities"],
        sweep_repository=setup["sweeps"],
        commodity_repository=setup["commodities"],
        call_provider=setup["call_provider"],
        call_gate=setup["call_gate"],
        settings=Settings(RETRY_DELAY_HOURS=4, MAX_CALL_ATTEMPTS=3),
    )


async def test_eligible_no_answer_call_is_retried(setup: dict) -> None:
    now = datetime(2026, 8, 22, 16, tzinfo=UTC)
    call = await _seed(setup, attempt_number=1, ended_at=now - timedelta(hours=10))

    result = await _use_case(setup).execute(now=now)

    assert result.retried_count == 1
    new_calls = await setup["calls"].list_by_sweep_id(call.sweep_id)
    attempt_numbers = sorted(c.attempt_number for c in new_calls)
    assert attempt_numbers == [1, 2]

    sweep = await setup["sweeps"].get_by_id(call.sweep_id)
    assert sweep is not None
    assert sweep.status == SweepStatus.IN_PROGRESS

    assert len(setup["call_provider"].calls) == 1


async def test_call_at_max_attempts_is_not_retried_and_stays_failed(setup: dict) -> None:
    now = datetime(2026, 8, 22, 16, tzinfo=UTC)
    call = await _seed(setup, attempt_number=3, ended_at=now - timedelta(hours=10))

    result = await _use_case(setup).execute(now=now)

    assert result.retried_count == 0
    calls = await setup["calls"].list_by_sweep_id(call.sweep_id)
    assert len(calls) == 1
    assert calls[0].status == CallStatus.NO_ANSWER
    assert len(setup["call_provider"].calls) == 0


async def test_call_too_recent_is_not_retried_yet(setup: dict) -> None:
    now = datetime(2026, 8, 22, 16, tzinfo=UTC)
    await _seed(setup, attempt_number=1, ended_at=now - timedelta(hours=1))

    result = await _use_case(setup).execute(now=now)

    assert result.retried_count == 0
    assert len(setup["call_provider"].calls) == 0


async def test_nothing_is_retried_while_the_call_engine_is_disabled(setup: dict) -> None:
    setup["call_gate"] = FakeCallGate(enabled=False)
    now = datetime(2026, 8, 22, 16, tzinfo=UTC)
    await _seed(setup, attempt_number=1, ended_at=now - timedelta(hours=10))

    result = await _use_case(setup).execute(now=now)

    assert result.retried_count == 0
    assert len(setup["call_provider"].calls) == 0
