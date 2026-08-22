"""Repository port for Commodity."""

from typing import TYPE_CHECKING, Protocol
from uuid import UUID

from app.domain.entities.commodity import Commodity

if TYPE_CHECKING:
    from app.application.use_cases.list_commodities import CommodityFilter


class CommodityRepositoryPort(Protocol):
    async def get_by_id(self, commodity_id: UUID) -> Commodity | None: ...

    async def add(self, commodity: Commodity) -> Commodity: ...

    async def update(self, commodity: Commodity) -> Commodity: ...

    async def list_all(self) -> list[Commodity]: ...

    async def list_by_filter(self, commodity_filter: "CommodityFilter") -> list[Commodity]: ...
