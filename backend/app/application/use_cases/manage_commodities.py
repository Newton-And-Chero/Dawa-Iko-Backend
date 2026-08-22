"""Commodity add/edit and priority-watchlist tagging."""

from dataclasses import dataclass, field
from uuid import UUID

from app.application.ports.commodity_repository import CommodityRepositoryPort
from app.core.exceptions import NotFoundError
from app.domain.entities.commodity import Commodity
from app.domain.enums import CommodityCategory


@dataclass
class NewCommodity:
    name: str
    category: CommodityCategory
    keml_code: str | None = None
    aliases: list[str] = field(default_factory=list)
    is_priority_watchlist: bool = False


@dataclass
class CommodityEdit:
    name: str | None = None
    category: CommodityCategory | None = None
    keml_code: str | None = None
    aliases: list[str] | None = None


class ManageCommoditiesUseCase:
    def __init__(self, commodity_repository: CommodityRepositoryPort) -> None:
        self._commodity_repository = commodity_repository

    async def add_commodity(self, new_commodity: NewCommodity) -> Commodity:
        commodity = Commodity(
            name=new_commodity.name,
            category=new_commodity.category,
            keml_code=new_commodity.keml_code,
            aliases=list(new_commodity.aliases),
            is_priority_watchlist=new_commodity.is_priority_watchlist,
        )
        return await self._commodity_repository.add(commodity)

    async def edit_commodity(self, commodity_id: UUID, edit: CommodityEdit) -> Commodity:
        commodity = await self._commodity_repository.get_by_id(commodity_id)
        if commodity is None:
            raise NotFoundError(f"commodity {commodity_id} not found")

        if edit.name is not None:
            commodity.name = edit.name
        if edit.category is not None:
            commodity.category = edit.category
        if edit.keml_code is not None:
            commodity.keml_code = edit.keml_code
        if edit.aliases is not None:
            commodity.aliases = list(edit.aliases)

        return await self._commodity_repository.update(commodity)

    async def set_priority_watchlist(
        self, commodity_id: UUID, is_priority_watchlist: bool
    ) -> Commodity:
        commodity = await self._commodity_repository.get_by_id(commodity_id)
        if commodity is None:
            raise NotFoundError(f"commodity {commodity_id} not found")

        commodity.is_priority_watchlist = is_priority_watchlist
        return await self._commodity_repository.update(commodity)
