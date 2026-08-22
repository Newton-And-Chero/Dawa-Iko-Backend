"""Seed the database with mock Kenyan facility/commodity data.

Usage: uv run python -m scripts.seed_db
"""

import asyncio
import json
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from app.application.use_cases.import_facilities import ImportFacilitiesUseCase, ImportResult
from app.application.use_cases.manage_commodities import ManageCommoditiesUseCase, NewCommodity
from app.domain.enums import CommodityCategory
from app.infrastructure.db.repositories.commodity_repository import SqlAlchemyCommodityRepository
from app.infrastructure.db.repositories.facility_repository import SqlAlchemyFacilityRepository
from app.infrastructure.db.session import async_session_factory
from app.infrastructure.facility_import.factory import DEFAULT_SEED_FILES, SEED_DATA_DIR
from app.infrastructure.facility_import.mock_kmhfl_adapter import MockKMHFLAdapter

COMMODITY_SEED_FILE = SEED_DATA_DIR / "commodities_keml.json"


@dataclass
class SeedSummary:
    facilities: ImportResult
    commodities_added: int
    commodities_skipped: int


async def _seed_commodities(session: AsyncSession) -> tuple[int, int]:
    repository = SqlAlchemyCommodityRepository(session)
    manage = ManageCommoditiesUseCase(repository)
    existing_keml_codes = {c.keml_code for c in await repository.list_all() if c.keml_code}

    payload = json.loads(COMMODITY_SEED_FILE.read_text())
    added = 0
    skipped = 0
    for raw in payload["commodities"]:
        if raw.get("keml_code") in existing_keml_codes:
            skipped += 1
            continue
        await manage.add_commodity(
            NewCommodity(
                name=raw["name"],
                category=CommodityCategory(raw["category"]),
                keml_code=raw.get("keml_code"),
                aliases=list(raw.get("aliases", [])),
                is_priority_watchlist=raw.get("is_priority_watchlist", False),
            )
        )
        added += 1
    return added, skipped


async def run_seed(session: AsyncSession) -> SeedSummary:
    """Run facility import + commodity seeding against the given session.

    Idempotent: a second run against the same DB reports 0 new facilities
    (all duplicates by phone) and 0 new commodities (all already seeded by
    keml_code).
    """
    facility_repository = SqlAlchemyFacilityRepository(session)
    import_port = MockKMHFLAdapter(seed_paths=DEFAULT_SEED_FILES)
    facility_result = await ImportFacilitiesUseCase(import_port, facility_repository).execute()

    commodities_added, commodities_skipped = await _seed_commodities(session)

    return SeedSummary(
        facilities=facility_result,
        commodities_added=commodities_added,
        commodities_skipped=commodities_skipped,
    )


async def main() -> None:
    async with async_session_factory() as session:
        summary = await run_seed(session)

    print(
        f"facilities: {summary.facilities.imported_count} imported, "
        f"{summary.facilities.skipped_duplicate_count} skipped as duplicates"
    )
    print(
        f"commodities: {summary.commodities_added} added, "
        f"{summary.commodities_skipped} skipped as already seeded"
    )


if __name__ == "__main__":
    asyncio.run(main())
