from app.application.use_cases.list_commodities import CommodityFilter, ListCommoditiesUseCase
from app.application.use_cases.manage_commodities import ManageCommoditiesUseCase, NewCommodity
from app.domain.enums import CommodityCategory
from tests.application.fakes import InMemoryCommodityRepository


async def _seeded_repository() -> InMemoryCommodityRepository:
    repository = InMemoryCommodityRepository()
    manage = ManageCommoditiesUseCase(repository)
    await manage.add_commodity(
        NewCommodity(
            name="Carbetocin",
            category=CommodityCategory.ESSENTIAL_MEDICINE,
            aliases=["PPH drug", "pitocin alternative"],
            is_priority_watchlist=True,
        )
    )
    await manage.add_commodity(
        NewCommodity(
            name="Oxytocin",
            category=CommodityCategory.ESSENTIAL_MEDICINE,
            aliases=["Pitocin"],
            is_priority_watchlist=False,
        )
    )
    return repository


async def test_list_all_with_no_filter() -> None:
    use_case = ListCommoditiesUseCase(await _seeded_repository())

    results = await use_case.execute()

    assert len(results) == 2


async def test_filter_by_priority_watchlist() -> None:
    use_case = ListCommoditiesUseCase(await _seeded_repository())

    results = await use_case.execute(CommodityFilter(is_priority_watchlist=True))

    assert [c.name for c in results] == ["Carbetocin"]


async def test_alias_fuzzy_search_matches_carbetocin() -> None:
    use_case = ListCommoditiesUseCase(await _seeded_repository())

    results = await use_case.execute(CommodityFilter(search="PPH drug"))

    assert [c.name for c in results] == ["Carbetocin"]


async def test_search_is_case_insensitive_substring() -> None:
    use_case = ListCommoditiesUseCase(await _seeded_repository())

    results = await use_case.execute(CommodityFilter(search="pitocin"))

    assert {c.name for c in results} == {"Carbetocin", "Oxytocin"}
