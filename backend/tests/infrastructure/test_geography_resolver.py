from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.entities.facility import Facility
from app.domain.enums import FacilitySource, FacilityType
from app.domain.value_objects.geography_scope import (
    CountyScope,
    NearestNScope,
    RadiusScope,
    SubCountyScope,
    WardScope,
)
from app.infrastructure.db.repositories.facility_repository import SqlAlchemyFacilityRepository
from app.infrastructure.geo.postgis_geography_resolver import PostGISGeographyResolver

_ORIGIN_LAT, _ORIGIN_LNG = -0.5, 37.28


def _facility(name: str, **overrides: object) -> Facility:
    defaults: dict[str, object] = dict(
        name=name,
        type=FacilityType.DISPENSARY,
        county="Kirinyaga",
        sub_county="Kirinyaga Central",
        ward="Kerugoya",
        gps_lat=_ORIGIN_LAT,
        gps_lng=_ORIGIN_LNG,
        phone_number="+254700000001",
        source=FacilitySource.KMHFL,
    )
    defaults.update(overrides)
    return Facility(**defaults)  # type: ignore[arg-type]


async def _seed(session: AsyncSession) -> dict[str, Facility]:
    repo = SqlAlchemyFacilityRepository(session)
    near = await repo.add(
        _facility("Near", gps_lat=_ORIGIN_LAT + 0.001, gps_lng=_ORIGIN_LNG + 0.001)
    )
    far = await repo.add(
        _facility(
            "Far",
            sub_county="Mwea",
            ward="Wamumu",
            gps_lat=-1.3,
            gps_lng=36.8,
            phone_number="+254700000002",
        )
    )
    other_county = await repo.add(
        _facility(
            "Nairobi Facility",
            county="Nairobi",
            sub_county="Westlands",
            ward="Karura",
            gps_lat=-1.26,
            gps_lng=36.81,
            phone_number="+254700000003",
        )
    )
    closed = await repo.add(
        _facility(
            "Closed Dispensary",
            gps_lat=_ORIGIN_LAT + 0.0005,
            gps_lng=_ORIGIN_LNG + 0.0005,
            phone_number="+254700000004",
            operational_status=False,
        )
    )
    return {"near": near, "far": far, "other_county": other_county, "closed": closed}


async def test_resolve_by_county(db_session: AsyncSession) -> None:
    facilities = await _seed(db_session)
    resolver = PostGISGeographyResolver(db_session)

    resolved = await resolver.resolve(CountyScope(county="Kirinyaga"))

    resolved_ids = {f.id for f in resolved}
    assert facilities["near"].id in resolved_ids
    assert facilities["far"].id in resolved_ids
    assert facilities["other_county"].id not in resolved_ids
    assert facilities["closed"].id not in resolved_ids


async def test_resolve_by_sub_county(db_session: AsyncSession) -> None:
    facilities = await _seed(db_session)
    resolver = PostGISGeographyResolver(db_session)

    resolved = await resolver.resolve(SubCountyScope(sub_county="Mwea"))

    assert {f.id for f in resolved} == {facilities["far"].id}


async def test_resolve_by_ward(db_session: AsyncSession) -> None:
    facilities = await _seed(db_session)
    resolver = PostGISGeographyResolver(db_session)

    resolved = await resolver.resolve(WardScope(ward="Kerugoya"))

    assert {f.id for f in resolved} == {facilities["near"].id}


async def test_resolve_by_radius(db_session: AsyncSession) -> None:
    facilities = await _seed(db_session)
    resolver = PostGISGeographyResolver(db_session)

    resolved = await resolver.resolve(RadiusScope(lat=_ORIGIN_LAT, lng=_ORIGIN_LNG, radius_km=5.0))

    resolved_ids = {f.id for f in resolved}
    assert facilities["near"].id in resolved_ids
    assert facilities["far"].id not in resolved_ids
    assert facilities["closed"].id not in resolved_ids


async def test_resolve_nearest_n_orders_by_distance_and_limits(db_session: AsyncSession) -> None:
    facilities = await _seed(db_session)
    resolver = PostGISGeographyResolver(db_session)

    resolved = await resolver.resolve(NearestNScope(lat=_ORIGIN_LAT, lng=_ORIGIN_LNG, n=1))

    assert len(resolved) == 1
    assert resolved[0].id == facilities["near"].id
