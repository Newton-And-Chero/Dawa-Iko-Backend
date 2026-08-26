"""SQLAlchemy implementation of SweepRepositoryPort."""

from uuid import UUID

from sqlalchemy import Text, cast, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.use_cases.list_sweeps import SweepFilter
from app.core.exceptions import NotFoundError
from app.domain.entities.sweep import Sweep
from app.domain.enums import SweepStatus
from app.infrastructure.db.models import SweepModel


def _to_domain(model: SweepModel) -> Sweep:
    return Sweep(
        id=model.id,
        commodity_id=model.commodity_id,
        geography_scope=dict(model.geography_scope),
        trigger_type=model.trigger_type,
        status=model.status,
        requester_id=model.requester_id,
        created_at=model.created_at,
    )


def _to_model(sweep: Sweep) -> SweepModel:
    return SweepModel(
        id=sweep.id,
        commodity_id=sweep.commodity_id,
        geography_scope=dict(sweep.geography_scope),
        trigger_type=sweep.trigger_type,
        status=sweep.status,
        requester_id=sweep.requester_id,
        created_at=sweep.created_at,
    )


class SqlAlchemySweepRepository:
    """Implements SweepRepositoryPort."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, sweep_id: UUID) -> Sweep | None:
        model = await self._session.get(SweepModel, sweep_id)
        return _to_domain(model) if model is not None else None

    async def add(self, sweep: Sweep) -> Sweep:
        model = _to_model(sweep)
        self._session.add(model)
        await self._session.commit()
        await self._session.refresh(model)
        return _to_domain(model)

    async def list_all(self) -> list[Sweep]:
        result = await self._session.execute(select(SweepModel))
        return [_to_domain(m) for m in result.scalars().all()]

    async def list_by_filter(self, sweep_filter: SweepFilter) -> list[Sweep]:
        stmt = select(SweepModel)
        if sweep_filter.commodity_id is not None:
            stmt = stmt.where(SweepModel.commodity_id == sweep_filter.commodity_id)
        if sweep_filter.status is not None:
            stmt = stmt.where(SweepModel.status == sweep_filter.status)
        if sweep_filter.date_from is not None:
            stmt = stmt.where(SweepModel.created_at >= sweep_filter.date_from)
        if sweep_filter.date_to is not None:
            stmt = stmt.where(SweepModel.created_at <= sweep_filter.date_to)
        if sweep_filter.geography is not None:
            stmt = stmt.where(
                cast(SweepModel.geography_scope, Text).ilike(f"%{sweep_filter.geography}%")
            )
        result = await self._session.execute(stmt.order_by(SweepModel.created_at.desc()))
        return [_to_domain(m) for m in result.scalars().all()]

    async def update_status(self, sweep_id: UUID, status: SweepStatus) -> None:
        model = await self._session.get(SweepModel, sweep_id)
        if model is None:
            raise NotFoundError(f"sweep {sweep_id} not found")
        model.status = status
        await self._session.commit()
