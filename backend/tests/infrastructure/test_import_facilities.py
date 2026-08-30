from sqlalchemy.ext.asyncio import AsyncSession

from app.application.use_cases.import_facilities import ImportFacilitiesUseCase
from app.infrastructure.db.repositories.facility_repository import SqlAlchemyFacilityRepository
from app.infrastructure.facility_import.factory import DEFAULT_SEED_FILES
from app.infrastructure.facility_import.mock_kmhfl_adapter import MockKMHFLAdapter


async def test_seed_import_is_idempotent(db_session: AsyncSession) -> None:
    repository = SqlAlchemyFacilityRepository(db_session)
    adapter = MockKMHFLAdapter(seed_paths=DEFAULT_SEED_FILES)
    use_case = ImportFacilitiesUseCase(adapter, repository)

    first_run = await use_case.execute()
    assert first_run.imported_count > 0
    assert first_run.skipped_duplicate_count == 0

    second_run = await use_case.execute()
    assert second_run.imported_count == 0
    assert second_run.skipped_duplicate_count == first_run.imported_count


async def test_import_can_be_scoped_to_a_county(db_session: AsyncSession) -> None:
    repository = SqlAlchemyFacilityRepository(db_session)
    adapter = MockKMHFLAdapter(seed_paths=DEFAULT_SEED_FILES)
    use_case = ImportFacilitiesUseCase(adapter, repository)

    result = await use_case.execute(county="Kirinyaga")

    facilities = await repository.list_all()
    assert result.imported_count == len(facilities)
    assert all(f.county == "Kirinyaga" for f in facilities)
