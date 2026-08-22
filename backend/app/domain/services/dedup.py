"""Facility duplicate detection. Pure function — no DB, no framework."""

from app.domain.entities.facility import Facility
from app.domain.entities.facility_import_record import FacilityImportRecord
from app.domain.services.geo import haversine_meters
from app.domain.services.phone import normalize_phone

# Two facilities this close together are treated as the same physical site
# even if their phone numbers differ (e.g. a re-import with a corrected line).
_DEFAULT_RADIUS_METERS = 100.0


def is_duplicate(
    candidate: FacilityImportRecord,
    existing: Facility,
    radius_meters: float = _DEFAULT_RADIUS_METERS,
) -> bool:
    """A candidate import record is a duplicate of an existing facility when
    either their phone numbers match (regardless of formatting) or they sit
    within ``radius_meters`` of each other.
    """
    if normalize_phone(candidate.phone_number) == normalize_phone(existing.phone_number):
        return True

    distance = haversine_meters(
        candidate.gps_lat, candidate.gps_lng, existing.gps_lat, existing.gps_lng
    )
    return distance <= radius_meters
