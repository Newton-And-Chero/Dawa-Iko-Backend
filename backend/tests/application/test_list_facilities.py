from app.application.use_cases.list_facilities import FacilityFilter, ListFacilitiesUseCase
from app.application.use_cases.manage_facilities import ManageFacilitiesUseCase, NewFacility
from app.domain.enums import FacilityType
from tests.application.fakes import InMemoryFacilityRepository


async def _seeded_repository() -> InMemoryFacilityRepository:
    repository = InMemoryFacilityRepository()
    manage = ManageFacilitiesUseCase(repository)
    await manage.add_facility(
        NewFacility(
            name="Kerugoya County Referral Hospital",
            type=FacilityType.PUBLIC,
            county="Kirinyaga",
            sub_county="Kirinyaga Central",
            ward="Kerugoya",
            gps_lat=-0.5,
            gps_lng=37.28,
            phone_number="+254700000001",
        )
    )
    await manage.add_facility(
        NewFacility(
            name="Baraka Chemist",
            type=FacilityType.PRIVATE_CHEMIST,
            county="Kirinyaga",
            sub_county="Kirinyaga Central",
            ward="Kutus",
            gps_lat=-0.6,
            gps_lng=37.30,
            phone_number="+254700000002",
        )
    )
    await manage.add_facility(
        NewFacility(
            name="Westlands Dispensary",
            type=FacilityType.DISPENSARY,
            county="Nairobi",
            sub_county="Westlands",
            ward="Karura",
            gps_lat=-1.26,
            gps_lng=36.81,
            phone_number="+254700000003",
        )
    )
    return repository


async def test_list_all_with_no_filter() -> None:
    use_case = ListFacilitiesUseCase(await _seeded_repository())

    results = await use_case.execute()

    assert len(results) == 3


async def test_filter_by_county() -> None:
    use_case = ListFacilitiesUseCase(await _seeded_repository())

    results = await use_case.execute(FacilityFilter(county="Kirinyaga"))

    assert {f.name for f in results} == {"Kerugoya County Referral Hospital", "Baraka Chemist"}


async def test_filter_by_type() -> None:
    use_case = ListFacilitiesUseCase(await _seeded_repository())

    results = await use_case.execute(FacilityFilter(type=FacilityType.PRIVATE_CHEMIST))

    assert [f.name for f in results] == ["Baraka Chemist"]


async def test_filter_by_ward() -> None:
    use_case = ListFacilitiesUseCase(await _seeded_repository())

    results = await use_case.execute(FacilityFilter(ward="Karura"))

    assert [f.name for f in results] == ["Westlands Dispensary"]
