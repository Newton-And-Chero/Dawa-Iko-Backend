from typing import TYPE_CHECKING, Protocol
from uuid import UUID

from app.domain.entities.facility import Facility

if TYPE_CHECKING:
    from app.application.use_cases.list_facilities import FacilityFilter


class FacilityRepositoryPort(Protocol):
    async def get_by_id(self, facility_id: UUID) -> Facility | None: ...

    async def add(self, facility: Facility) -> Facility: ...

    async def update(self, facility: Facility) -> Facility: ...

    async def list_all(self) -> list[Facility]: ...

    async def list_by_filter(self, facility_filter: "FacilityFilter") -> list[Facility]: ...
