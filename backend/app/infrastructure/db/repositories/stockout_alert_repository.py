from uuid import UUID

from sqlalchemy import Text, cast, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.use_cases.list_escalations import EscalationFilter
from app.core.exceptions import NotFoundError
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
        acknowledgment_note=model.acknowledgment_note,
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
        acknowledgment_note=stockout_alert.acknowledgment_note,
    )


class SqlAlchemyStockoutAlertRepository:
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

    async def update(self, stockout_alert: StockoutAlert) -> StockoutAlert:
        model = await self._session.get(StockoutAlertModel, stockout_alert.id)
        if model is None:
            raise NotFoundError(f"stockout alert {stockout_alert.id} not found")
        updated = _to_model(stockout_alert)
        for column in StockoutAlertModel.__table__.columns:
            if column.name == "id":
                continue
            setattr(model, column.name, getattr(updated, column.name))
        await self._session.commit()
        await self._session.refresh(model)
        return _to_domain(model)

    async def list_all(self) -> list[StockoutAlert]:
        result = await self._session.execute(select(StockoutAlertModel))
        return [_to_domain(m) for m in result.scalars().all()]

    async def list_by_filter(self, escalation_filter: EscalationFilter) -> list[StockoutAlert]:
        stmt = select(StockoutAlertModel)
        if escalation_filter.commodity_id is not None:
            stmt = stmt.where(StockoutAlertModel.commodity_id == escalation_filter.commodity_id)
        if escalation_filter.status is not None:
            stmt = stmt.where(StockoutAlertModel.status == escalation_filter.status)
        if escalation_filter.severity is not None:
            stmt = stmt.where(StockoutAlertModel.severity == escalation_filter.severity)
        if escalation_filter.geography is not None:
            stmt = stmt.where(
                cast(StockoutAlertModel.geography, Text).ilike(f"%{escalation_filter.geography}%")
            )
        result = await self._session.execute(stmt.order_by(StockoutAlertModel.triggered_at.desc()))
        return [_to_domain(m) for m in result.scalars().all()]
