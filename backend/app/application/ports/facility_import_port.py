from typing import Protocol

from app.domain.entities.facility_import_record import FacilityImportRecord


class FacilityImportPort(Protocol):
    async def fetch_facilities(self, county: str | None = None) -> list[FacilityImportRecord]: ...
