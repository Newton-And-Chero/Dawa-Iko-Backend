"""FacilityImportRecord — what an import source hands back, pre-persistence."""

from dataclasses import dataclass

from app.domain.enums import FacilitySource, FacilityType


@dataclass
class FacilityImportRecord:
    name: str
    type: FacilityType
    county: str
    sub_county: str
    ward: str
    gps_lat: float
    gps_lng: float
    phone_number: str
    source: FacilitySource
    kmhfl_code: str | None = None
