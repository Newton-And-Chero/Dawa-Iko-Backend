from dataclasses import dataclass, field
from uuid import UUID, uuid4

from app.domain.enums import CommodityCategory


@dataclass
class Commodity:
    name: str
    category: CommodityCategory
    id: UUID = field(default_factory=uuid4)
    keml_code: str | None = None
    aliases: list[str] = field(default_factory=list)
    is_priority_watchlist: bool = False
