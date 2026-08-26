"""BuildPatientMatchResponseUseCase — ranking (in-stock first, i.e. filtered
to only in-stock, then by the documented distance/confidence tiebreaker)."""

from decimal import Decimal
from uuid import uuid4

import pytest

from app.application.use_cases.build_patient_match_response import (
    BuildPatientMatchResponseUseCase,
)
from app.core.exceptions import NotFoundError
from app.domain.entities.availability_result import AvailabilityResult
from app.domain.entities.call import Call
from app.domain.entities.facility import Facility
from app.domain.entities.sweep import Sweep
from app.domain.enums import FacilitySource, FacilityType, StockStatus, SweepTrigger
from app.domain.value_objects.geography_scope import (
    CountyScope,
    RadiusScope,
    geography_scope_to_dict,
)
from tests.application.fakes import (
    InMemoryAvailabilityResultRepository,
    InMemoryCallRepository,
    InMemoryFacilityRepository,
    InMemorySweepRepository,
)


def _facility(n: int, *, lat: float, lng: float) -> Facility:
    return Facility(
        name=f"Facility {n}",
        type=FacilityType.DISPENSARY,
        county="Kirinyaga",
        sub_county="Mwea",
        ward="Wamumu",
        gps_lat=lat,
        gps_lng=lng,
        phone_number=f"+2547000{n:05d}",
        source=FacilitySource.KMHFL,
    )


@pytest.fixture
def setup() -> dict:
    return {
        "sweeps": InMemorySweepRepository(),
        "calls": InMemoryCallRepository(),
        "results": InMemoryAvailabilityResultRepository(),
        "facilities": InMemoryFacilityRepository(),
    }


def _use_case(setup: dict) -> BuildPatientMatchResponseUseCase:
    return BuildPatientMatchResponseUseCase(
        sweep_repository=setup["sweeps"],
        call_repository=setup["calls"],
        availability_result_repository=setup["results"],
        facility_repository=setup["facilities"],
    )


async def test_unknown_sweep_raises(setup: dict) -> None:
    with pytest.raises(NotFoundError):
        await _use_case(setup).execute(uuid4())


async def test_only_in_stock_results_are_returned(setup: dict) -> None:
    sweep = await setup["sweeps"].add(
        Sweep(
            commodity_id=uuid4(),
            geography_scope=geography_scope_to_dict(CountyScope(county="Kirinyaga")),
            trigger_type=SweepTrigger.ON_DEMAND,
        )
    )
    near = await setup["facilities"].add(_facility(0, lat=-0.6849, lng=37.3667))
    far_but_out_of_stock = await setup["facilities"].add(_facility(1, lat=-0.7, lng=37.4))

    in_stock_call = await setup["calls"].add(Call(sweep_id=sweep.id, facility_id=near.id))
    await setup["results"].add(
        AvailabilityResult(
            call_id=in_stock_call.id,
            facility_id=near.id,
            commodity_id=sweep.commodity_id,
            in_stock=StockStatus.YES,
            price_kes=Decimal("100"),
        )
    )
    out_of_stock_call = await setup["calls"].add(
        Call(sweep_id=sweep.id, facility_id=far_but_out_of_stock.id)
    )
    await setup["results"].add(
        AvailabilityResult(
            call_id=out_of_stock_call.id,
            facility_id=far_but_out_of_stock.id,
            commodity_id=sweep.commodity_id,
            in_stock=StockStatus.NO,
        )
    )

    matches = await _use_case(setup).execute(sweep.id)

    assert [m.facility_id for m in matches] == [near.id]
    assert matches[0].price_kes == Decimal("100")


async def test_matches_ranked_by_distance_then_confidence(setup: dict) -> None:
    origin = RadiusScope(lat=-0.6849, lng=37.3667, radius_km=20)
    sweep = await setup["sweeps"].add(
        Sweep(
            commodity_id=uuid4(),
            geography_scope=geography_scope_to_dict(origin),
            trigger_type=SweepTrigger.ON_DEMAND,
        )
    )
    near = await setup["facilities"].add(_facility(0, lat=-0.6849, lng=37.3667))
    far = await setup["facilities"].add(_facility(1, lat=-0.9, lng=37.6))

    for facility, confidence in [(far, 0.99), (near, 0.5)]:
        call = await setup["calls"].add(Call(sweep_id=sweep.id, facility_id=facility.id))
        await setup["results"].add(
            AvailabilityResult(
                call_id=call.id,
                facility_id=facility.id,
                commodity_id=sweep.commodity_id,
                in_stock=StockStatus.YES,
                confidence=confidence,
            )
        )

    matches = await _use_case(setup).execute(sweep.id)

    # Distance wins over confidence: the near facility (lower confidence)
    # still ranks first.
    assert [m.facility_id for m in matches] == [near.id, far.id]


async def test_no_origin_point_falls_back_to_confidence_ranking(setup: dict) -> None:
    sweep = await setup["sweeps"].add(
        Sweep(
            commodity_id=uuid4(),
            geography_scope=geography_scope_to_dict(CountyScope(county="Kirinyaga")),
            trigger_type=SweepTrigger.ON_DEMAND,
        )
    )
    low_confidence = await setup["facilities"].add(_facility(0, lat=-0.6849, lng=37.3667))
    high_confidence = await setup["facilities"].add(_facility(1, lat=-0.7, lng=37.4))

    for facility, confidence in [(low_confidence, 0.4), (high_confidence, 0.9)]:
        call = await setup["calls"].add(Call(sweep_id=sweep.id, facility_id=facility.id))
        await setup["results"].add(
            AvailabilityResult(
                call_id=call.id,
                facility_id=facility.id,
                commodity_id=sweep.commodity_id,
                in_stock=StockStatus.YES,
                confidence=confidence,
            )
        )

    matches = await _use_case(setup).execute(sweep.id)

    assert [m.facility_id for m in matches] == [high_confidence.id, low_confidence.id]
    assert all(m.distance_meters is None for m in matches)
