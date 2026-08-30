from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

from app.application.ports.facility_repository import FacilityRepositoryPort
from app.core.exceptions import NotFoundError
from app.domain.entities.facility import Facility
from app.domain.enums import FacilitySource, FacilityType, PhoneVerificationStatus
from app.domain.services.phone import validate_phone


@dataclass
class NewFacility:
    name: str
    type: FacilityType
    county: str
    sub_county: str
    ward: str
    gps_lat: float
    gps_lng: float
    phone_number: str
    kmhfl_code: str | None = None


@dataclass
class FacilityEdit:
    name: str | None = None
    type: FacilityType | None = None
    county: str | None = None
    sub_county: str | None = None
    ward: str | None = None
    gps_lat: float | None = None
    gps_lng: float | None = None
    phone_number: str | None = None
    kmhfl_code: str | None = None
    operational_status: bool | None = None


class ManageFacilitiesUseCase:
    def __init__(self, facility_repository: FacilityRepositoryPort) -> None:
        self._facility_repository = facility_repository

    async def add_facility(self, new_facility: NewFacility) -> Facility:
        phone = validate_phone(new_facility.phone_number)
        facility = Facility(
            name=new_facility.name,
            type=new_facility.type,
            county=new_facility.county,
            sub_county=new_facility.sub_county,
            ward=new_facility.ward,
            gps_lat=new_facility.gps_lat,
            gps_lng=new_facility.gps_lng,
            phone_number=phone,
            source=FacilitySource.MANUAL,
            kmhfl_code=new_facility.kmhfl_code,
        )
        return await self._facility_repository.add(facility)

    async def edit_facility(self, facility_id: UUID, edit: FacilityEdit) -> Facility:
        facility = await self._facility_repository.get_by_id(facility_id)
        if facility is None:
            raise NotFoundError(f"facility {facility_id} not found")

        if edit.name is not None:
            facility.name = edit.name
        if edit.type is not None:
            facility.type = edit.type
        if edit.county is not None:
            facility.county = edit.county
        if edit.sub_county is not None:
            facility.sub_county = edit.sub_county
        if edit.ward is not None:
            facility.ward = edit.ward
        if edit.gps_lat is not None:
            facility.gps_lat = edit.gps_lat
        if edit.gps_lng is not None:
            facility.gps_lng = edit.gps_lng
        if edit.phone_number is not None:
            facility.phone_number = validate_phone(edit.phone_number)
        if edit.kmhfl_code is not None:
            facility.kmhfl_code = edit.kmhfl_code
        if edit.operational_status is not None:
            facility.operational_status = edit.operational_status

        return await self._facility_repository.update(facility)

    async def set_phone_verification_status(
        self, facility_id: UUID, status: PhoneVerificationStatus
    ) -> Facility:
        facility = await self._facility_repository.get_by_id(facility_id)
        if facility is None:
            raise NotFoundError(f"facility {facility_id} not found")

        facility.phone_verification_status = status
        if status == PhoneVerificationStatus.VERIFIED:
            facility.last_verified_at = datetime.now(UTC)

        return await self._facility_repository.update(facility)
