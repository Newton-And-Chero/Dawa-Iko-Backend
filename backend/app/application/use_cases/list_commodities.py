"""List/filter commodities."""

from dataclasses import dataclass

from app.application.ports.commodity_repository import CommodityRepositoryPort
from app.domain.entities.commodity import Commodity
from app.domain.enums import CommodityCategory


@dataclass
class CommodityFilter:
    category: CommodityCategory | None = None
    is_priority_watchlist: bool | None = None
    # Fuzzy match against name or any alias, e.g. "PPH drug" -> carbetocin.
    search: str | None = None


class ListCommoditiesUseCase:
    def __init__(self, commodity_repository: CommodityRepositoryPort) -> None:
        self._commodity_repository = commodity_repository

    async def execute(self, commodity_filter: CommodityFilter | None = None) -> list[Commodity]:
        return await self._commodity_repository.list_by_filter(
            commodity_filter or CommodityFilter()
        )
