from typing import TYPE_CHECKING, Protocol
from uuid import UUID

from app.domain.entities.stockout_alert import StockoutAlert

if TYPE_CHECKING:
    from app.application.use_cases.list_escalations import EscalationFilter


class StockoutAlertRepositoryPort(Protocol):
    async def get_by_id(self, stockout_alert_id: UUID) -> StockoutAlert | None: ...

    async def add(self, stockout_alert: StockoutAlert) -> StockoutAlert: ...

    async def update(self, stockout_alert: StockoutAlert) -> StockoutAlert: ...

    async def list_all(self) -> list[StockoutAlert]: ...

    async def list_by_filter(
        self, escalation_filter: "EscalationFilter"
    ) -> list[StockoutAlert]: ...
