from dataclasses import dataclass
from uuid import UUID

from app.application.ports.commodity_repository import CommodityRepositoryPort
from app.core.exceptions import NotFoundError
from app.domain.entities.commodity import Commodity
from app.domain.enums import CommodityCategory


@dataclass
class CommodityFilter:
    category: CommodityCategory | None = None
    is_priority_watchlist: bool | None = None
    search: str | None = None


class ListCommoditiesUseCase:
    def __init__(self, commodity_repository: CommodityRepositoryPort) -> None:
        self._commodity_repository = commodity_repository

    async def execute(self, commodity_filter: CommodityFilter | None = None) -> list[Commodity]:
        return await self._commodity_repository.list_by_filter(
            commodity_filter or CommodityFilter()
        )

    async def get(self, commodity_id: UUID) -> Commodity:
        commodity = await self._commodity_repository.get_by_id(commodity_id)
        if commodity is None:
            raise NotFoundError(f"commodity {commodity_id} not found")
        return commodity
