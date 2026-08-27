"""`_resolve_call_phones` — the hackathon call guardrail behind
`CALL_DEMO_REDIRECT_NUMBERS`. Pure, no DB."""

from app.application.use_cases._sweep_dispatch import _resolve_call_phones
from app.domain.entities.facility import Facility
from app.domain.enums import FacilitySource, FacilityType


def _facility(phone: str) -> Facility:
    return Facility(
        name="F",
        type=FacilityType.DISPENSARY,
        county="Kirinyaga",
        sub_county="Mwea",
        ward="Wamumu",
        gps_lat=-0.68,
        gps_lng=37.36,
        phone_number=phone,
        source=FacilitySource.KMHFL,
    )


def test_no_redirect_dials_each_facility_at_its_own_number() -> None:
    facs = [_facility("+254700000001"), _facility("+254700000002")]

    kept, phones = _resolve_call_phones(facs, None)

    assert kept == facs
    assert phones == ["+254700000001", "+254700000002"]


def test_empty_redirect_list_is_treated_as_no_redirect() -> None:
    facs = [_facility("+254700000001")]

    kept, phones = _resolve_call_phones(facs, [])

    assert kept == facs
    assert phones == ["+254700000001"]


def test_redirect_caps_chunk_to_number_count_and_reroutes() -> None:
    facs = [_facility(f"+25470000000{i}") for i in range(5)]

    kept, phones = _resolve_call_phones(facs, ["+254792036343", "+254720168641"])

    assert len(kept) == 2
    assert kept == facs[:2]
    assert phones == ["+254792036343", "+254720168641"]


def test_redirect_normalizes_local_format_numbers() -> None:
    facs = [_facility("+254700000001")]

    _, phones = _resolve_call_phones(facs, ["0792036343"])

    assert phones == ["+254792036343"]


def test_fewer_facilities_than_redirect_numbers_keeps_one_to_one() -> None:
    facs = [_facility("+254700000001")]

    kept, phones = _resolve_call_phones(facs, ["+254792036343", "+254720168641"])

    assert len(kept) == 1
    assert phones == ["+254792036343"]
