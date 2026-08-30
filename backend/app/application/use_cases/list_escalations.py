from dataclasses import dataclass
from uuid import UUID

from app.application.ports.stockout_alert_repository import StockoutAlertRepositoryPort
from app.domain.entities.stockout_alert import StockoutAlert
from app.domain.enums import EscalationSeverity, EscalationStatus


@dataclass
class EscalationFilter:
    commodity_id: UUID | None = None
    status: EscalationStatus | None = None
    severity: EscalationSeverity | None = None
    geography: str | None = None


class ListEscalationsUseCase:
    def __init__(self, stockout_alert_repository: StockoutAlertRepositoryPort) -> None:
        self._alerts = stockout_alert_repository

    async def execute(
        self, escalation_filter: EscalationFilter | None = None
    ) -> list[StockoutAlert]:
        return await self._alerts.list_by_filter(escalation_filter or EscalationFilter())
