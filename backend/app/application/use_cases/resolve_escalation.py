"""Subscriber/analyst marks a StockoutAlert resolved (PROJECT.md 2.5)."""

from uuid import UUID

from app.application.ports.realtime_event_bus_port import RealtimeEventBusPort
from app.application.ports.stockout_alert_repository import StockoutAlertRepositoryPort
from app.application.realtime_events import publish_alert_updated_event
from app.core.exceptions import NotFoundError
from app.domain.entities.stockout_alert import StockoutAlert
from app.domain.enums import EscalationStatus


class ResolveEscalationUseCase:
    def __init__(
        self,
        stockout_alert_repository: StockoutAlertRepositoryPort,
        realtime_event_bus: RealtimeEventBusPort,
    ) -> None:
        self._alerts = stockout_alert_repository
        self._realtime_event_bus = realtime_event_bus

    async def execute(self, stockout_alert_id: UUID, note: str | None = None) -> StockoutAlert:
        alert = await self._alerts.get_by_id(stockout_alert_id)
        if alert is None:
            raise NotFoundError(f"stockout alert {stockout_alert_id} not found")

        alert.status = EscalationStatus.RESOLVED
        if note is not None:
            alert.acknowledgment_note = note
        updated = await self._alerts.update(alert)
        await publish_alert_updated_event(self._realtime_event_bus, updated)
        return updated
