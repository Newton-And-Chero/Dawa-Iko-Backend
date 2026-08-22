"""List/filter facilities."""

from dataclasses import dataclass

from app.application.ports.facility_repository import FacilityRepositoryPort
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
