"""SQLAlchemy implementation of FacilityRepositoryPort."""

from uuid import UUID

from geoalchemy2.shape import from_shape, to_shape
from shapely.geometry import Point
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.use_cases.list_facilities import FacilityFilter
from app.core.exceptions import NotFoundError
from app.domain.entities.facility import Facility
from app.infrastructure.db.models import FacilityModel


def facility_model_to_domain(model: FacilityModel) -> Facility:
    point = to_shape(model.location)
    return Facility(
        id=model.id,
        name=model.name,
        type=model.type,
        county=model.county,
        sub_county=model.sub_county,
        ward=model.ward,
        gps_lat=point.y,
        gps_lng=point.x,
        phone_number=model.phone_number,
        source=model.source,
        kmhfl_code=model.kmhfl_code,
        operational_status=model.operational_status,
        last_verified_at=model.last_verified_at,
        reliability_score=model.reliability_score,
        phone_verification_status=model.phone_verification_status,
    )


def _to_model(facility: Facility) -> FacilityModel:
    return FacilityModel(
        id=facility.id,
        name=facility.name,
        type=facility.type,
        county=facility.county,
        sub_county=facility.sub_county,
        ward=facility.ward,
        location=from_shape(Point(facility.gps_lng, facility.gps_lat), srid=4326),
        phone_number=facility.phone_number,
        source=facility.source,
        kmhfl_code=facility.kmhfl_code,
        operational_status=facility.operational_status,
        last_verified_at=facility.last_verified_at,
        reliability_score=facility.reliability_score,
        phone_verification_status=facility.phone_verification_status,
    )


class SqlAlchemyFacilityRepository:
    """Implements FacilityRepositoryPort."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, facility_id: UUID) -> Facility | None:
        model = await self._session.get(FacilityModel, facility_id)
        return facility_model_to_domain(model) if model is not None else None

    async def add(self, facility: Facility) -> Facility:
        model = _to_model(facility)
        self._session.add(model)
        await self._session.commit()
        await self._session.refresh(model)
        return facility_model_to_domain(model)

    async def update(self, facility: Facility) -> Facility:
        model = await self._session.get(FacilityModel, facility.id)
        if model is None:
            raise NotFoundError(f"facility {facility.id} not found")
        updated = _to_model(facility)
        for column in FacilityModel.__table__.columns:
            if column.name == "id":
                continue
            setattr(model, column.name, getattr(updated, column.name))
        await self._session.commit()
        await self._session.refresh(model)
        return facility_model_to_domain(model)

    async def list_all(self) -> list[Facility]:
        result = await self._session.execute(select(FacilityModel))
        return [facility_model_to_domain(m) for m in result.scalars().all()]

    async def list_by_filter(self, facility_filter: FacilityFilter) -> list[Facility]:
        stmt = select(FacilityModel)
        if facility_filter.county is not None:
            stmt = stmt.where(FacilityModel.county == facility_filter.county)
        if facility_filter.sub_county is not None:
            stmt = stmt.where(FacilityModel.sub_county == facility_filter.sub_county)
        if facility_filter.ward is not None:
            stmt = stmt.where(FacilityModel.ward == facility_filter.ward)
        if facility_filter.type is not None:
            stmt = stmt.where(FacilityModel.type == facility_filter.type)
        if facility_filter.source is not None:
            stmt = stmt.where(FacilityModel.source == facility_filter.source)
        result = await self._session.execute(stmt)
        return [facility_model_to_domain(m) for m in result.scalars().all()]
