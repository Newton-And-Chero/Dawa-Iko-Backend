"""Mock facility-directory adapter — reads local seed JSON files.

Stands in for a real KMHFL export until RealKMHFLAdapter is implemented.
"""

import json
from pathlib import Path

from app.domain.entities.facility_import_record import FacilityImportRecord
from app.domain.enums import FacilitySource, FacilityType


class MockKMHFLAdapter:
    """Implements FacilityImportPort by reading data/seed/*.json seed files."""

    def __init__(self, seed_paths: list[Path]) -> None:
        self._seed_paths = seed_paths

    async def fetch_facilities(self, county: str | None = None) -> list[FacilityImportRecord]:
        records = [record for path in self._seed_paths for record in self._load(path)]
        if county is not None:
            records = [r for r in records if r.county.lower() == county.lower()]
        return records

    @staticmethod
    def _load(path: Path) -> list[FacilityImportRecord]:
        payload = json.loads(path.read_text())
        return [
            FacilityImportRecord(
                name=raw["name"],
                type=FacilityType(raw["facility_type"]),
                county=raw["county"],
                sub_county=raw["sub_county"],
                ward=raw["ward"],
                gps_lat=raw["gps_lat"],
                gps_lng=raw["gps_lng"],
                phone_number=raw["phone_number"],
                source=FacilitySource(raw["source"]),
                kmhfl_code=raw.get("kmhfl_code"),
            )
            for raw in payload["facilities"]
        ]
