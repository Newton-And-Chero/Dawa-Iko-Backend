"""PostGISGeographyResolver — resolves a GeographyScope into a candidate
facility list via PostGIS queries against `Facility.location` (GIST-indexed,
Sprint 01): exact-match filters for county/sub_county/ward, `ST_DWithin` for
radius, and `ST_Distance` order-by + `LIMIT` for nearest-N.

Distances are computed by casting the geometry column to `geography` so
`ST_DWithin`/`ST_Distance` operate in meters rather than raw SRID-4326
degrees.
"""

from geoalchemy2 import Geography
from sqlalchemy import cast, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.entities.facility import Facility
from app.domain.value_objects.geography_scope import (
    CountyScope,
    GeographyScope,
    NearestNScope,
    RadiusScope,
    SubCountyScope,
    WardScope,
)
from app.infrastructure.db.models import FacilityModel
from app.infrastructure.db.repositories.facility_repository import facility_model_to_domain


class PostGISGeographyResolver:
    """Implements GeographyResolverPort."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def resolve(self, geography: GeographyScope) -> list[Facility]:
        stmt = select(FacilityModel).where(FacilityModel.operational_status.is_(True))

        match geography:
            case CountyScope(county=county):
                stmt = stmt.where(FacilityModel.county == county)
            case SubCountyScope(sub_county=sub_county):
                stmt = stmt.where(FacilityModel.sub_county == sub_county)
            case WardScope(ward=ward):
                stmt = stmt.where(FacilityModel.ward == ward)
            case RadiusScope(lat=lat, lng=lng, radius_km=radius_km):
                point = func.ST_SetSRID(func.ST_MakePoint(lng, lat), 4326)
                stmt = stmt.where(
                    func.ST_DWithin(
                        cast(FacilityModel.location, Geography),
                        cast(point, Geography),
                        radius_km * 1000,
                    )
                )
            case NearestNScope(lat=lat, lng=lng, n=n):
                point = func.ST_SetSRID(func.ST_MakePoint(lng, lat), 4326)
                stmt = stmt.order_by(
                    func.ST_Distance(
                        cast(FacilityModel.location, Geography), cast(point, Geography)
                    )
                ).limit(n)

        result = await self._session.execute(stmt)
        return [facility_model_to_domain(m) for m in result.scalars().all()]
