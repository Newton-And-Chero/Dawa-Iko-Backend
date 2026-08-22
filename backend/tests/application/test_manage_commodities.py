from uuid import uuid4

import pytest

from app.application.use_cases.manage_commodities import (
    CommodityEdit,
    ManageCommoditiesUseCase,
    NewCommodity,
)
from app.core.exceptions import NotFoundError
from app.domain.enums import CommodityCategory
from tests.application.fakes import InMemoryCommodityRepository


def _new_commodity(**overrides: object) -> NewCommodity:
    defaults: dict[str, object] = dict(
        name="Carbetocin",
        category=CommodityCategory.ESSENTIAL_MEDICINE,
        keml_code="KEML-SYN-0001",
        aliases=["PPH drug"],
        is_priority_watchlist=False,
    )
    defaults.update(overrides)
    return NewCommodity(**defaults)  # type: ignore[arg-type]


async def test_add_commodity() -> None:
    use_case = ManageCommoditiesUseCase(InMemoryCommodityRepository())

    commodity = await use_case.add_commodity(_new_commodity())

    assert commodity.name == "Carbetocin"
    assert commodity.aliases == ["PPH drug"]


async def test_edit_commodity_updates_only_given_fields() -> None:
    use_case = ManageCommoditiesUseCase(InMemoryCommodityRepository())
    commodity = await use_case.add_commodity(_new_commodity())

    edited = await use_case.edit_commodity(commodity.id, CommodityEdit(aliases=["PPH drug", "OXY"]))

    assert edited.aliases == ["PPH drug", "OXY"]
    assert edited.name == commodity.name


async def test_edit_unknown_commodity_raises_not_found() -> None:
    use_case = ManageCommoditiesUseCase(InMemoryCommodityRepository())

    with pytest.raises(NotFoundError):
        await use_case.edit_commodity(uuid4(), CommodityEdit(name="x"))


async def test_toggle_priority_watchlist() -> None:
    use_case = ManageCommoditiesUseCase(InMemoryCommodityRepository())
    commodity = await use_case.add_commodity(_new_commodity(is_priority_watchlist=False))

    tagged = await use_case.set_priority_watchlist(commodity.id, True)
    assert tagged.is_priority_watchlist is True

    untagged = await use_case.set_priority_watchlist(commodity.id, False)
    assert untagged.is_priority_watchlist is False
