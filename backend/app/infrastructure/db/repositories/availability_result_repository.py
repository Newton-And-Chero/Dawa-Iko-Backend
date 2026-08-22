"""SQLAlchemy implementation of AvailabilityResultRepositoryPort."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.domain.entities.availability_result import AvailabilityResult
from app.infrastructure.db.models import AvailabilityResultModel


def _to_domain(model: AvailabilityResultModel) -> AvailabilityResult:
    return AvailabilityResult(
        id=model.id,
        call_id=model.call_id,
        facility_id=model.facility_id,
        commodity_id=model.commodity_id,
        in_stock=model.in_stock,
        quantity_band=model.quantity_band,
        price_kes=model.price_kes,
        last_restock_date=model.last_restock_date,
        can_hold=model.can_hold,
        hold_duration_hours=model.hold_duration_hours,
        hold_reference_code=model.hold_reference_code,
        confidence=model.confidence,
        notes=model.notes,
        created_at=model.created_at,
    )


def _to_model(availability_result: AvailabilityResult) -> AvailabilityResultModel:
    return AvailabilityResultModel(
        id=availability_result.id,
        call_id=availability_result.call_id,
        facility_id=availability_result.facility_id,
        commodity_id=availability_result.commodity_id,
        in_stock=availability_result.in_stock,
        quantity_band=availability_result.quantity_band,
        price_kes=availability_result.price_kes,
        last_restock_date=availability_result.last_restock_date,
        can_hold=availability_result.can_hold,
        hold_duration_hours=availability_result.hold_duration_hours,
        hold_reference_code=availability_result.hold_reference_code,
        confidence=availability_result.confidence,
        notes=availability_result.notes,
        created_at=availability_result.created_at,
    )


class SqlAlchemyAvailabilityResultRepository:
    """Implements AvailabilityResultRepositoryPort."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, availability_result_id: UUID) -> AvailabilityResult | None:
        model = await self._session.get(AvailabilityResultModel, availability_result_id)
        return _to_domain(model) if model is not None else None

    async def get_by_call_id(self, call_id: UUID) -> AvailabilityResult | None:
        stmt = select(AvailabilityResultModel).where(AvailabilityResultModel.call_id == call_id)
        result = await self._session.execute(stmt)
        model = result.scalars().first()
        return _to_domain(model) if model is not None else None

    async def add(self, availability_result: AvailabilityResult) -> AvailabilityResult:
        model = _to_model(availability_result)
        self._session.add(model)
        await self._session.commit()
        await self._session.refresh(model)
        return _to_domain(model)

    async def update(self, availability_result: AvailabilityResult) -> AvailabilityResult:
        model = await self._session.get(AvailabilityResultModel, availability_result.id)
        if model is None:
            raise NotFoundError(f"availability result {availability_result.id} not found")
        updated = _to_model(availability_result)
        for column in AvailabilityResultModel.__table__.columns:
            if column.name in ("id", "created_at"):
                continue
            setattr(model, column.name, getattr(updated, column.name))
        await self._session.commit()
        await self._session.refresh(model)
        return _to_domain(model)

    async def list_all(self) -> list[AvailabilityResult]:
        result = await self._session.execute(select(AvailabilityResultModel))
        return [_to_domain(m) for m in result.scalars().all()]
