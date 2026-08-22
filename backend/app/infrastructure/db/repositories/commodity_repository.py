"""SQLAlchemy implementation of CommodityRepositoryPort."""

from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.use_cases.list_commodities import CommodityFilter
from app.core.exceptions import NotFoundError
from app.domain.entities.commodity import Commodity
from app.infrastructure.db.models import CommodityModel


def _to_domain(model: CommodityModel) -> Commodity:
    return Commodity(
        id=model.id,
        name=model.name,
        category=model.category,
        keml_code=model.keml_code,
        aliases=list(model.aliases),
        is_priority_watchlist=model.is_priority_watchlist,
    )


def _to_model(commodity: Commodity) -> CommodityModel:
    return CommodityModel(
        id=commodity.id,
        name=commodity.name,
        category=commodity.category,
        keml_code=commodity.keml_code,
        aliases=list(commodity.aliases),
        is_priority_watchlist=commodity.is_priority_watchlist,
    )


class SqlAlchemyCommodityRepository:
    """Implements CommodityRepositoryPort."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, commodity_id: UUID) -> Commodity | None:
        model = await self._session.get(CommodityModel, commodity_id)
        return _to_domain(model) if model is not None else None

    async def add(self, commodity: Commodity) -> Commodity:
        model = _to_model(commodity)
        self._session.add(model)
        await self._session.commit()
        await self._session.refresh(model)
        return _to_domain(model)

    async def update(self, commodity: Commodity) -> Commodity:
        model = await self._session.get(CommodityModel, commodity.id)
        if model is None:
            raise NotFoundError(f"commodity {commodity.id} not found")
        updated = _to_model(commodity)
        for column in CommodityModel.__table__.columns:
            if column.name == "id":
                continue
            setattr(model, column.name, getattr(updated, column.name))
        await self._session.commit()
        await self._session.refresh(model)
        return _to_domain(model)

    async def list_all(self) -> list[Commodity]:
        result = await self._session.execute(select(CommodityModel))
        return [_to_domain(m) for m in result.scalars().all()]

    async def list_by_filter(self, commodity_filter: CommodityFilter) -> list[Commodity]:
        stmt = select(CommodityModel)
        if commodity_filter.category is not None:
            stmt = stmt.where(CommodityModel.category == commodity_filter.category)
        if commodity_filter.is_priority_watchlist is not None:
            stmt = stmt.where(
                CommodityModel.is_priority_watchlist == commodity_filter.is_priority_watchlist
            )
        if commodity_filter.search is not None:
            pattern = f"%{commodity_filter.search}%"
            stmt = stmt.where(
                or_(
                    CommodityModel.name.ilike(pattern),
                    func.array_to_string(CommodityModel.aliases, ",").ilike(pattern),
                )
            )
        result = await self._session.execute(stmt)
        return [_to_domain(m) for m in result.scalars().all()]
