"""SQLAlchemy implementation of StockoutAlertRepositoryPort."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.entities.stockout_alert import StockoutAlert
from app.infrastructure.db.models import StockoutAlertModel


def _to_domain(model: StockoutAlertModel) -> StockoutAlert:
    return StockoutAlert(
        id=model.id,
        commodity_id=model.commodity_id,
        geography=dict(model.geography),
        severity=model.severity,
        facilities_checked_count=model.facilities_checked_count,
        facilities_with_stock_count=model.facilities_with_stock_count,
        status=model.status,
        triggered_at=model.triggered_at,
    )


def _to_model(stockout_alert: StockoutAlert) -> StockoutAlertModel:
    return StockoutAlertModel(
        id=stockout_alert.id,
        commodity_id=stockout_alert.commodity_id,
        geography=dict(stockout_alert.geography),
        severity=stockout_alert.severity,
        facilities_checked_count=stockout_alert.facilities_checked_count,
        facilities_with_stock_count=stockout_alert.facilities_with_stock_count,
        status=stockout_alert.status,
        triggered_at=stockout_alert.triggered_at,
    )


class SqlAlchemyStockoutAlertRepository:
    """Implements StockoutAlertRepositoryPort."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, stockout_alert_id: UUID) -> StockoutAlert | None:
        model = await self._session.get(StockoutAlertModel, stockout_alert_id)
        return _to_domain(model) if model is not None else None

    async def add(self, stockout_alert: StockoutAlert) -> StockoutAlert:
        model = _to_model(stockout_alert)
        self._session.add(model)
        await self._session.commit()
        await self._session.refresh(model)
        return _to_domain(model)

    async def list_all(self) -> list[StockoutAlert]:
        result = await self._session.execute(select(StockoutAlertModel))
        return [_to_domain(m) for m in result.scalars().all()]
