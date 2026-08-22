"""Port for pulling facility records from an external directory source."""

from typing import Protocol

from app.domain.entities.facility_import_record import FacilityImportRecord


class FacilityImportPort(Protocol):
    async def fetch_facilities(self, county: str | None = None) -> list[FacilityImportRecord]:
        """Return facility records, optionally narrowed to a single county."""
        ...
