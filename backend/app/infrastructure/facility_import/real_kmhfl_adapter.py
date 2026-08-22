"""Real KMHFL API adapter — stub only.

Not implemented this sprint (PROJECT.md's KMHFL cross-reference is a stretch
goal). Wire this up against the live KMHFL API when that work starts.
"""

from app.domain.entities.facility_import_record import FacilityImportRecord


class RealKMHFLAdapter:
    """Implements FacilityImportPort against the live KMHFL API. Stub only."""

    def __init__(self, base_url: str, api_key: str) -> None:
        self._base_url = base_url
        self._api_key = api_key

    async def fetch_facilities(self, county: str | None = None) -> list[FacilityImportRecord]:
        raise NotImplementedError("real KMHFL adapter not implemented — see workflows/02")
