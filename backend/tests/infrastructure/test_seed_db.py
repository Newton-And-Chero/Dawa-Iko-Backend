import json

from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.db.repositories.commodity_repository import SqlAlchemyCommodityRepository
from app.infrastructure.db.repositories.facility_repository import SqlAlchemyFacilityRepository
from app.infrastructure.facility_import.factory import DEFAULT_SEED_FILES
from app.infrastructure.facility_import.mock_kmhfl_adapter import MockKMHFLAdapter
from scripts.seed_db import COMMODITY_SEED_FILE, run_seed


async def test_seed_db_leaves_expected_row_counts(db_session: AsyncSession) -> None:
    expected_facility_count = sum(
        len(json.loads(path.read_text())["facilities"]) for path in DEFAULT_SEED_FILES
    )
    expected_commodity_count = len(json.loads(COMMODITY_SEED_FILE.read_text())["commodities"])

    summary = await run_seed(db_session)

    assert summary.facilities.imported_count == expected_facility_count
    assert summary.commodities_added == expected_commodity_count

    facilities = await SqlAlchemyFacilityRepository(db_session).list_all()
    commodities = await SqlAlchemyCommodityRepository(db_session).list_all()
    assert len(facilities) == expected_facility_count
    assert len(commodities) == expected_commodity_count


async def test_seed_db_is_idempotent(db_session: AsyncSession) -> None:
    first = await run_seed(db_session)
    second = await run_seed(db_session)

    assert second.facilities.imported_count == 0
    assert second.facilities.skipped_duplicate_count == first.facilities.imported_count
    assert second.commodities_added == 0
    assert second.commodities_skipped == first.commodities_added


async def test_mock_adapter_reads_all_seed_files() -> None:
    adapter = MockKMHFLAdapter(seed_paths=DEFAULT_SEED_FILES)
    records = await adapter.fetch_facilities()
    assert len(records) > 0
