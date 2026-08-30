from datetime import UTC, datetime, timedelta

from app.domain.entities.facility import Facility
from app.domain.enums import CallListIntent, CallStatus, FacilitySource, FacilityType
from app.domain.services.call_list_policy import (
    chunk,
    is_cooldown_blocked,
    is_eligible_for_retry,
    prioritize,
)
from app.domain.value_objects.geography_scope import CountyScope, NearestNScope, RadiusScope


def _facility(name: str, facility_type: FacilityType, lat: float, lng: float) -> Facility:
    return Facility(
        name=name,
        type=facility_type,
        county="Kirinyaga",
        sub_county="Mwea",
        ward="Wamumu",
        gps_lat=lat,
        gps_lng=lng,
        phone_number="+254700000001",
        source=FacilitySource.KMHFL,
    )


def test_prioritize_orders_public_before_private_with_no_point_reference() -> None:
    private = _facility("Private Chemist", FacilityType.PRIVATE_CHEMIST, -0.68, 37.36)
    public = _facility("Public Dispensary", FacilityType.DISPENSARY, -0.69, 37.37)

    ordered = prioritize(
        [private, public], CountyScope(county="Kirinyaga"), CallListIntent.PUBLIC_FIRST
    )

    assert [f.name for f in ordered] == ["Public Dispensary", "Private Chemist"]


def test_prioritize_private_first_intent_reverses_type_order() -> None:
    private = _facility("Private Chemist", FacilityType.PRIVATE_CHEMIST, -0.68, 37.36)
    public = _facility("Public Dispensary", FacilityType.DISPENSARY, -0.69, 37.37)

    ordered = prioritize(
        [public, private], CountyScope(county="Kirinyaga"), CallListIntent.PRIVATE_FIRST
    )

    assert [f.name for f in ordered] == ["Private Chemist", "Public Dispensary"]


def test_prioritize_orders_by_distance_when_scope_has_point_reference() -> None:
    near = _facility("Near", FacilityType.PRIVATE_CHEMIST, -0.685, 37.367)
    far = _facility("Far", FacilityType.PUBLIC, -1.3, 36.8)

    ordered = prioritize(
        [far, near],
        RadiusScope(lat=-0.6849, lng=37.3667, radius_km=10),
        CallListIntent.PUBLIC_FIRST,
    )

    assert [f.name for f in ordered] == ["Near", "Far"]


def test_prioritize_distance_takes_precedence_over_type_intent() -> None:
    near_private = _facility("Near Private", FacilityType.PRIVATE_CHEMIST, -0.685, 37.367)
    far_public = _facility("Far Public", FacilityType.PUBLIC, -1.3, 36.8)

    ordered = prioritize(
        [far_public, near_private],
        NearestNScope(lat=-0.6849, lng=37.3667, n=2),
        CallListIntent.PUBLIC_FIRST,
    )

    assert [f.name for f in ordered] == ["Near Private", "Far Public"]


def test_chunk_exact_multiple() -> None:
    facilities = [_facility(str(i), FacilityType.PUBLIC, 0, 0) for i in range(4)]
    chunks = chunk(facilities, 2)
    assert [len(c) for c in chunks] == [2, 2]


def test_chunk_with_remainder() -> None:
    facilities = [_facility(str(i), FacilityType.PUBLIC, 0, 0) for i in range(5)]
    chunks = chunk(facilities, 2)
    assert [len(c) for c in chunks] == [2, 2, 1]


def test_chunk_single_item() -> None:
    facilities = [_facility("only", FacilityType.PUBLIC, 0, 0)]
    chunks = chunk(facilities, 50)
    assert chunks == [facilities]


def test_chunk_empty_list() -> None:
    assert chunk([], 50) == []


def test_chunk_preserves_order() -> None:
    facilities = [_facility(str(i), FacilityType.PUBLIC, 0, 0) for i in range(3)]
    chunks = chunk(facilities, 2)
    assert [f.name for c in chunks for f in c] == ["0", "1", "2"]


def test_cooldown_blocks_recent_call() -> None:
    now = datetime(2026, 8, 22, tzinfo=UTC)
    last_call = now - timedelta(hours=1)
    assert is_cooldown_blocked(last_call, now, cooldown_hours=24) is True


def test_cooldown_allows_call_outside_window() -> None:
    now = datetime(2026, 8, 22, tzinfo=UTC)
    last_call = now - timedelta(hours=25)
    assert is_cooldown_blocked(last_call, now, cooldown_hours=24) is False


def test_cooldown_allows_facility_never_called() -> None:
    now = datetime(2026, 8, 22, tzinfo=UTC)
    assert is_cooldown_blocked(None, now, cooldown_hours=24) is False


def test_retry_ineligible_for_completed_call() -> None:
    now = datetime(2026, 8, 22, 12, tzinfo=UTC)
    ended_at = now - timedelta(hours=10)
    assert is_eligible_for_retry(CallStatus.COMPLETED, 1, ended_at, now, 4, 3) is False


def test_retry_ineligible_at_max_attempts() -> None:
    now = datetime(2026, 8, 22, 12, tzinfo=UTC)
    ended_at = now - timedelta(hours=10)
    assert is_eligible_for_retry(CallStatus.NO_ANSWER, 3, ended_at, now, 4, 3) is False


def test_retry_ineligible_before_delay_elapses() -> None:
    now = datetime(2026, 8, 22, 12, tzinfo=UTC)
    ended_at = now - timedelta(hours=1)
    assert is_eligible_for_retry(CallStatus.NO_ANSWER, 1, ended_at, now, 4, 3) is False


def test_retry_ineligible_same_hour_of_day_as_failed_attempt() -> None:
    now = datetime(2026, 8, 23, 12, tzinfo=UTC)
    ended_at = datetime(2026, 8, 22, 12, tzinfo=UTC)
    assert is_eligible_for_retry(CallStatus.NO_ANSWER, 1, ended_at, now, 4, 3) is False


def test_retry_eligible_after_delay_and_different_hour() -> None:
    now = datetime(2026, 8, 22, 16, tzinfo=UTC)
    ended_at = datetime(2026, 8, 22, 10, tzinfo=UTC)
    assert is_eligible_for_retry(CallStatus.NO_ANSWER, 1, ended_at, now, 4, 3) is True


def test_retry_ineligible_without_ended_at() -> None:
    now = datetime(2026, 8, 22, 12, tzinfo=UTC)
    assert is_eligible_for_retry(CallStatus.FAILED, 1, None, now, 4, 3) is False
