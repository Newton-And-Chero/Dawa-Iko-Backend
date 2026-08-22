from app.domain.entities.facility import Facility
from app.domain.entities.facility_import_record import FacilityImportRecord
from app.domain.enums import FacilitySource, FacilityType
from app.domain.services.dedup import is_duplicate


def _existing(**overrides: object) -> Facility:
    defaults: dict[str, object] = dict(
        name="Kerugoya County Referral Hospital",
        type=FacilityType.PUBLIC,
        county="Kirinyaga",
        sub_county="Kirinyaga Central",
        ward="Kerugoya",
        gps_lat=-0.5,
        gps_lng=37.28,
        phone_number="+254700000001",
        source=FacilitySource.KMHFL,
    )
    defaults.update(overrides)
    return Facility(**defaults)  # type: ignore[arg-type]


def _candidate(**overrides: object) -> FacilityImportRecord:
    defaults: dict[str, object] = dict(
        name="Kerugoya County Referral Hospital",
        type=FacilityType.PUBLIC,
        county="Kirinyaga",
        sub_county="Kirinyaga Central",
        ward="Kerugoya",
        gps_lat=-0.5,
        gps_lng=37.28,
        phone_number="+254700000001",
        source=FacilitySource.KMHFL,
    )
    defaults.update(overrides)
    return FacilityImportRecord(**defaults)  # type: ignore[arg-type]


def test_exact_phone_match_is_duplicate() -> None:
    existing = _existing(gps_lat=-1.0, gps_lng=38.0)
    candidate = _candidate(gps_lat=5.0, gps_lng=5.0, phone_number="+254700000001")
    assert is_duplicate(candidate, existing) is True


def test_same_phone_different_formatting_is_duplicate() -> None:
    existing = _existing(phone_number="+254700000001", gps_lat=-1.0, gps_lng=38.0)
    candidate = _candidate(phone_number="0700000001", gps_lat=5.0, gps_lng=5.0)
    assert is_duplicate(candidate, existing) is True


def test_close_gps_different_phone_is_duplicate() -> None:
    existing = _existing(gps_lat=-0.5, gps_lng=37.28, phone_number="+254700000001")
    candidate = _candidate(gps_lat=-0.500001, gps_lng=37.280001, phone_number="+254700000002")
    assert is_duplicate(candidate, existing) is True


def test_far_gps_different_phone_is_not_duplicate() -> None:
    existing = _existing(gps_lat=-0.5, gps_lng=37.28, phone_number="+254700000001")
    candidate = _candidate(gps_lat=-1.3, gps_lng=36.8, phone_number="+254700000002")
    assert is_duplicate(candidate, existing) is False
