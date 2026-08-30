from app.domain.entities.facility import Facility
from app.domain.entities.facility_import_record import FacilityImportRecord
from app.domain.services.geo import haversine_meters
from app.domain.services.phone import normalize_phone

_DEFAULT_RADIUS_METERS = 100.0


def is_duplicate(
    candidate: FacilityImportRecord,
    existing: Facility,
    radius_meters: float = _DEFAULT_RADIUS_METERS,
) -> bool:
    if normalize_phone(candidate.phone_number) == normalize_phone(existing.phone_number):
        return True

    distance = haversine_meters(
        candidate.gps_lat, candidate.gps_lng, existing.gps_lat, existing.gps_lng
    )
    return distance <= radius_meters
