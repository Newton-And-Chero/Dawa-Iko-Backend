"""Import facilities from a FacilityImportPort, deduping against existing rows."""

from dataclasses import dataclass

from app.application.ports.facility_import_port import FacilityImportPort
from app.application.ports.facility_repository import FacilityRepositoryPort
from app.domain.entities.facility import Facility
from app.domain.services.dedup import is_duplicate
from app.domain.services.phone import validate_phone


@dataclass
class ImportResult:
    imported_count: int
    skipped_duplicate_count: int


class ImportFacilitiesUseCase:
    def __init__(
        self, import_port: FacilityImportPort, facility_repository: FacilityRepositoryPort
    ) -> None:
        self._import_port = import_port
        self._facility_repository = facility_repository

    async def execute(self, county: str | None = None) -> ImportResult:
        records = await self._import_port.fetch_facilities(county)
        existing = await self._facility_repository.list_all()

        imported_count = 0
        skipped_duplicate_count = 0

        for record in records:
            if any(is_duplicate(record, facility) for facility in existing):
                skipped_duplicate_count += 1
                continue

            facility = Facility(
                name=record.name,
                type=record.type,
                county=record.county,
                sub_county=record.sub_county,
                ward=record.ward,
                gps_lat=record.gps_lat,
                gps_lng=record.gps_lng,
                phone_number=validate_phone(record.phone_number),
                source=record.source,
                kmhfl_code=record.kmhfl_code,
            )
            added = await self._facility_repository.add(facility)
            existing.append(added)
            imported_count += 1

        return ImportResult(
            imported_count=imported_count, skipped_duplicate_count=skipped_duplicate_count
        )
