from datetime import datetime, timedelta

from app.domain.entities.facility import Facility
from app.domain.enums import CallListIntent, CallStatus, FacilityType
from app.domain.services.geo import haversine_meters
from app.domain.value_objects.geography_scope import GeographyScope, NearestNScope, RadiusScope

_PRIVATE_TYPES = {FacilityType.PRIVATE_CHEMIST}


def _type_rank(facility_type: FacilityType, intent: CallListIntent) -> int:
    is_private = facility_type in _PRIVATE_TYPES
    if intent == CallListIntent.PRIVATE_FIRST:
        return 0 if is_private else 1
    return 1 if is_private else 0


def prioritize(
    facilities: list[Facility],
    geography: GeographyScope,
    intent: CallListIntent = CallListIntent.PUBLIC_FIRST,
) -> list[Facility]:
    point: tuple[float, float] | None = None
    if isinstance(geography, RadiusScope | NearestNScope):
        point = (geography.lat, geography.lng)

    def sort_key(facility: Facility) -> tuple[float, int]:
        distance = (
            haversine_meters(point[0], point[1], facility.gps_lat, facility.gps_lng)
            if point is not None
            else 0.0
        )
        return (distance, _type_rank(facility.type, intent))

    return sorted(facilities, key=sort_key)


def chunk(facilities: list[Facility], max_per_task: int) -> list[list[Facility]]:
    if max_per_task <= 0:
        raise ValueError("max_per_task must be positive")
    return [facilities[i : i + max_per_task] for i in range(0, len(facilities), max_per_task)]


def is_cooldown_blocked(
    last_call_started_at: datetime | None, now: datetime, cooldown_hours: int
) -> bool:
    if last_call_started_at is None:
        return False
    return now - last_call_started_at < timedelta(hours=cooldown_hours)


def is_eligible_for_retry(
    status: CallStatus,
    attempt_number: int,
    ended_at: datetime | None,
    now: datetime,
    retry_delay_hours: int,
    max_attempts: int,
) -> bool:
    if status not in (CallStatus.NO_ANSWER, CallStatus.FAILED):
        return False
    if attempt_number >= max_attempts:
        return False
    if ended_at is None:
        return False
    if now - ended_at < timedelta(hours=retry_delay_hours):
        return False
    return now.hour != ended_at.hour
