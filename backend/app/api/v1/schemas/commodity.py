from uuid import UUID

from pydantic import BaseModel, Field

from app.domain.enums import CommodityCategory


class CommodityIn(BaseModel):
    name: str
    category: CommodityCategory
    keml_code: str | None = None
    aliases: list[str] = Field(default_factory=list)
    is_priority_watchlist: bool = False


class CommodityEditIn(BaseModel):
    name: str | None = None
    category: CommodityCategory | None = None
    keml_code: str | None = None
    aliases: list[str] | None = None


class WatchlistIn(BaseModel):
    is_priority_watchlist: bool


class CommodityOut(BaseModel):
    id: UUID
    name: str
    category: CommodityCategory
    keml_code: str | None
    aliases: list[str]
    is_priority_watchlist: bool
