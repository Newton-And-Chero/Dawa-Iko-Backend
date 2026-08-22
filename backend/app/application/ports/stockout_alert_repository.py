"""Repository port for StockoutAlert."""

from typing import Protocol
from uuid import UUID

from app.domain.entities.stockout_alert import StockoutAlert


class StockoutAlertRepositoryPort(Protocol):
    async def get_by_id(self, stockout_alert_id: UUID) -> StockoutAlert | None: ...

    async def add(self, stockout_alert: StockoutAlert) -> StockoutAlert: ...

    async def list_all(self) -> list[StockoutAlert]: ...
