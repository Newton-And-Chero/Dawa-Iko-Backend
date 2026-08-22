from uuid import uuid4

import pytest

from app.application.use_cases.manage_facilities import (
    FacilityEdit,
    ManageFacilitiesUseCase,
    NewFacility,
)
from app.core.exceptions import NotFoundError, ValidationError
from app.domain.enums import FacilitySource, FacilityType, PhoneVerificationStatus
from tests.application.fakes import InMemoryFacilityRepository


def _new_facility(**overrides: object) -> NewFacility:
    defaults: dict[str, object] = dict(
        name="Baraka Chemist",
        type=FacilityType.PRIVATE_CHEMIST,
        county="Kirinyaga",
        sub_county="Kirinyaga Central",
        ward="Kerugoya",
        gps_lat=-0.5,
        gps_lng=37.28,
        phone_number="+254700000099",
    )
    defaults.update(overrides)
    return NewFacility(**defaults)  # type: ignore[arg-type]


async def test_add_facility_sets_source_manual() -> None:
    use_case = ManageFacilitiesUseCase(InMemoryFacilityRepository())

    facility = await use_case.add_facility(_new_facility())

    assert facility.source == FacilitySource.MANUAL
    assert facility.phone_number == "+254700000099"


async def test_add_facility_rejects_invalid_phone() -> None:
    use_case = ManageFacilitiesUseCase(InMemoryFacilityRepository())

    with pytest.raises(ValidationError):
        await use_case.add_facility(_new_facility(phone_number="0712"))


async def test_add_facility_normalizes_local_phone_format() -> None:
    use_case = ManageFacilitiesUseCase(InMemoryFacilityRepository())

    facility = await use_case.add_facility(_new_facility(phone_number="0700000099"))

    assert facility.phone_number == "+254700000099"


async def test_edit_facility_updates_only_given_fields() -> None:
    use_case = ManageFacilitiesUseCase(InMemoryFacilityRepository())
    facility = await use_case.add_facility(_new_facility())

    edited = await use_case.edit_facility(facility.id, FacilityEdit(name="Baraka Chemist Ltd"))

    assert edited.name == "Baraka Chemist Ltd"
    assert edited.ward == facility.ward


async def test_edit_facility_rejects_invalid_phone() -> None:
    use_case = ManageFacilitiesUseCase(InMemoryFacilityRepository())
    facility = await use_case.add_facility(_new_facility())

    with pytest.raises(ValidationError):
        await use_case.edit_facility(facility.id, FacilityEdit(phone_number="not-a-phone"))


async def test_edit_unknown_facility_raises_not_found() -> None:
    use_case = ManageFacilitiesUseCase(InMemoryFacilityRepository())

    with pytest.raises(NotFoundError):
        await use_case.edit_facility(uuid4(), FacilityEdit(name="x"))


async def test_verify_phone_sets_status_and_last_verified_at() -> None:
    use_case = ManageFacilitiesUseCase(InMemoryFacilityRepository())
    facility = await use_case.add_facility(_new_facility())
    assert facility.phone_verification_status == PhoneVerificationStatus.UNVERIFIED

    verified = await use_case.set_phone_verification_status(
        facility.id, PhoneVerificationStatus.VERIFIED
    )

    assert verified.phone_verification_status == PhoneVerificationStatus.VERIFIED
    assert verified.last_verified_at is not None


async def test_mark_phone_bounced() -> None:
    use_case = ManageFacilitiesUseCase(InMemoryFacilityRepository())
    facility = await use_case.add_facility(_new_facility())

    bounced = await use_case.set_phone_verification_status(
        facility.id, PhoneVerificationStatus.BOUNCED
    )

    assert bounced.phone_verification_status == PhoneVerificationStatus.BOUNCED
