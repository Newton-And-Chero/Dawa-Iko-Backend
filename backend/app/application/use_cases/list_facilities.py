from dataclasses import dataclass
from uuid import UUID

from app.application.ports.facility_repository import FacilityRepositoryPort
from app.core.exceptions import NotFoundError
from app.domain.entities.facility import Facility
from app.domain.enums import FacilitySource, FacilityType


@dataclass
class FacilityFilter:
    county: str | None = None
    sub_county: str | None = None
    ward: str | None = None
    type: FacilityType | None = None
    source: FacilitySource | None = None


class ListFacilitiesUseCase:
    def __init__(self, facility_repository: FacilityRepositoryPort) -> None:
        self._facility_repository = facility_repository

    async def execute(self, facility_filter: FacilityFilter | None = None) -> list[Facility]:
        return await self._facility_repository.list_by_filter(facility_filter or FacilityFilter())

    async def get(self, facility_id: UUID) -> Facility:
        facility = await self._facility_repository.get_by_id(facility_id)
        if facility is None:
            raise NotFoundError(f"facility {facility_id} not found")
        return facility
