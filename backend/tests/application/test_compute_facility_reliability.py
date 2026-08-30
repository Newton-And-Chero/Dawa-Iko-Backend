from uuid import uuid4

import pytest

from app.application.use_cases.compute_facility_reliability import (
    ComputeFacilityReliabilityUseCase,
)
from app.domain.entities.facility import Facility
from app.domain.enums import FacilitySource, FacilityType
from app.domain.value_objects.analytics import FacilityCallStats
from tests.application.fakes import InMemoryAnalyticsRepository, InMemoryFacilityRepository


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


async def test_compute_for_facility_blends_answer_rate_and_confidence() -> None:
    facility_id = uuid4()
    analytics = InMemoryAnalyticsRepository()
    analytics.seed_facility_stats(
        FacilityCallStats(facility_id=facility_id, total_calls=10, completed_calls=8)
    )
    analytics.seed_confidences(facility_id, [0.8, 1.0])

    use_case = ComputeFacilityReliabilityUseCase(analytics, InMemoryFacilityRepository())
    result = await use_case.compute_for_facility(facility_id)

    assert result.answer_rate == 0.8
    assert result.avg_result_confidence == pytest.approx(0.9)
    assert result.reliability_score == pytest.approx(0.65 * 0.8 + 0.35 * 0.9, abs=1e-4)


async def test_compute_for_facility_with_no_results_uses_answer_rate_only() -> None:
    facility_id = uuid4()
    analytics = InMemoryAnalyticsRepository()
    analytics.seed_facility_stats(
        FacilityCallStats(facility_id=facility_id, total_calls=4, completed_calls=1)
    )

    use_case = ComputeFacilityReliabilityUseCase(analytics, InMemoryFacilityRepository())
    result = await use_case.compute_for_facility(facility_id)

    assert result.avg_result_confidence is None
    assert result.reliability_score == 0.25


async def test_recompute_and_persist_all_writes_score_back_onto_facility() -> None:
    facilities = InMemoryFacilityRepository()
    facility = await facilities.add(_facility())

    analytics = InMemoryAnalyticsRepository()
    analytics.seed_facility_stats(
        FacilityCallStats(facility_id=facility.id, total_calls=4, completed_calls=4)
    )

    use_case = ComputeFacilityReliabilityUseCase(analytics, facilities)
    await use_case.recompute_and_persist_all()

    updated = await facilities.get_by_id(facility.id)
    assert updated is not None
    assert updated.reliability_score == 1.0


async def test_recompute_and_persist_all_skips_facility_not_in_repository() -> None:
    facilities = InMemoryFacilityRepository()
    analytics = InMemoryAnalyticsRepository()
    analytics.seed_facility_stats(
        FacilityCallStats(facility_id=uuid4(), total_calls=2, completed_calls=1)
    )

    use_case = ComputeFacilityReliabilityUseCase(analytics, facilities)
    results = await use_case.recompute_and_persist_all()

    assert len(results) == 1
