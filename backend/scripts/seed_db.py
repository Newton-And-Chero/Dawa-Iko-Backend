"""Seed the database with mock Kenyan facility/commodity data, plus a fixed
set of test login accounts and alert subscribers so every role-gated screen
and the escalation/subscriber management screens have something to show
without a chicken-and-egg "no user exists yet to create the first user"
problem (`POST /users` is admin-only — see docs/api.md).

Usage: uv run python -m scripts.seed_db
"""

import asyncio
import json
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from app.application.use_cases.import_facilities import ImportFacilitiesUseCase, ImportResult
from app.application.use_cases.manage_commodities import ManageCommoditiesUseCase, NewCommodity
from app.application.use_cases.manage_subscribers import ManageSubscribersUseCase, NewSubscriber
from app.application.use_cases.manage_users import ManageUsersUseCase, NewUser
from app.domain.enums import CommodityCategory, NotificationChannel, UserRole
from app.infrastructure.db.repositories.commodity_repository import SqlAlchemyCommodityRepository
from app.infrastructure.db.repositories.facility_repository import SqlAlchemyFacilityRepository
from app.infrastructure.db.repositories.subscriber_repository import SqlAlchemySubscriberRepository
from app.infrastructure.db.repositories.user_repository import SqlAlchemyUserRepository
from app.infrastructure.db.session import async_session_factory
from app.infrastructure.facility_import.factory import DEFAULT_SEED_FILES, SEED_DATA_DIR
from app.infrastructure.facility_import.mock_kmhfl_adapter import MockKMHFLAdapter

COMMODITY_SEED_FILE = SEED_DATA_DIR / "commodities_keml.json"

# Fixed (not random) so re-running the script, or a frontend dev reading this
# file, always gets the same login. Never used outside `mock`-mode local/dev
# deployments — these credentials are not a secret worth rotating.
TEST_USER_PASSWORD = "testpass123"
TEST_USERS = [
    NewUser(
        name="Demo Admin",
        role=UserRole.ADMIN,
        phone_number="+254700000001",
        password=TEST_USER_PASSWORD,
        org="CALL-E Admin",
    ),
    NewUser(
        name="Demo Analyst",
        role=UserRole.ANALYST,
        phone_number="+254700000002",
        password=TEST_USER_PASSWORD,
        org="MOH Kirinyaga",
    ),
    NewUser(
        name="Demo Viewer",
        role=UserRole.VIEWER,
        phone_number="+254700000003",
        password=TEST_USER_PASSWORD,
        org="MOH Nairobi",
    ),
]

# keml_code here, resolved to a real commodity id at seed time (mirrors
# WATCHLIST_SWEEPS in app/workers/beat_schedule.py) — commodity UUIDs don't
# exist until commodities are seeded.
TEST_SUBSCRIBERS = [
    {
        "name": "Kirinyaga County Pharmacist",
        "notification_channel": NotificationChannel.SMS,
        "org": "MOH Kirinyaga",
        "phone": "+254700000010",
        "watchlist_keml_codes": ["KEML-SYN-0001"],  # Carbetocin
        "watchlist_geography": {"kind": "county", "county": "Kirinyaga"},
    },
    {
        "name": "Nairobi County Pharmacist",
        "notification_channel": NotificationChannel.SMS,
        "org": "MOH Nairobi",
        "phone": "+254700000011",
        "watchlist_keml_codes": ["KEML-SYN-0003"],  # Human Insulin (Soluble)
        "watchlist_geography": {"kind": "county", "county": "Nairobi"},
    },
    {
        "name": "MOH Webhook Integration",
        "notification_channel": NotificationChannel.WEBHOOK,
        "org": "Ministry of Health",
        "webhook_url": "https://example.org/moh-webhook",
        "watchlist_keml_codes": ["KEML-SYN-0001", "KEML-SYN-0003"],
        "watchlist_geography": {},
    },
]


@dataclass
class SeedSummary:
    facilities: ImportResult
    commodities_added: int
    commodities_skipped: int
    users_added: int
    users_skipped: int
    subscribers_added: int
    subscribers_skipped: int


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


async def _seed_users(session: AsyncSession) -> tuple[int, int]:
    repository = SqlAlchemyUserRepository(session)
    manage = ManageUsersUseCase(repository)

    added = 0
    skipped = 0
    for new_user in TEST_USERS:
        if await repository.get_by_phone_number(new_user.phone_number) is not None:
            skipped += 1
            continue
        await manage.add_user(new_user)
        added += 1
    return added, skipped


async def _seed_subscribers(session: AsyncSession) -> tuple[int, int]:
    commodity_repository = SqlAlchemyCommodityRepository(session)
    by_keml_code = {c.keml_code: c for c in await commodity_repository.list_all() if c.keml_code}

    subscriber_repository = SqlAlchemySubscriberRepository(session)
    manage = ManageSubscribersUseCase(subscriber_repository)
    existing_names = {s.name for s in await subscriber_repository.list_all()}

    added = 0
    skipped = 0
    for raw in TEST_SUBSCRIBERS:
        if raw["name"] in existing_names:
            skipped += 1
            continue
        watchlist_commodities = [
            by_keml_code[code].id
            for code in raw["watchlist_keml_codes"]
            if code in by_keml_code
        ]
        await manage.add_subscriber(
            NewSubscriber(
                name=raw["name"],
                notification_channel=raw["notification_channel"],
                org=raw.get("org"),
                phone=raw.get("phone"),
                email=raw.get("email"),
                webhook_url=raw.get("webhook_url"),
                watchlist_commodities=watchlist_commodities,
                watchlist_geography=raw["watchlist_geography"],
            )
        )
        added += 1
    return added, skipped


async def run_seed(session: AsyncSession) -> SeedSummary:
    """Run facility/commodity import, then test-user and test-subscriber
    seeding, against the given session.

    Idempotent: a second run against the same DB reports 0 new facilities
    (all duplicates by phone), 0 new commodities (all already seeded by
    keml_code), 0 new users (all already seeded by phone_number), and 0 new
    subscribers (all already seeded by name).
    """
    facility_repository = SqlAlchemyFacilityRepository(session)
    import_port = MockKMHFLAdapter(seed_paths=DEFAULT_SEED_FILES)
    facility_result = await ImportFacilitiesUseCase(import_port, facility_repository).execute()

    commodities_added, commodities_skipped = await _seed_commodities(session)
    # Users/subscribers seed independently of facilities/commodities, but
    # subscriber watchlists reference commodity ids, so commodities must be
    # seeded first.
    users_added, users_skipped = await _seed_users(session)
    subscribers_added, subscribers_skipped = await _seed_subscribers(session)

    return SeedSummary(
        facilities=facility_result,
        commodities_added=commodities_added,
        commodities_skipped=commodities_skipped,
        users_added=users_added,
        users_skipped=users_skipped,
        subscribers_added=subscribers_added,
        subscribers_skipped=subscribers_skipped,
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
    print(
        f"users: {summary.users_added} added, "
        f"{summary.users_skipped} skipped as already seeded"
    )
    print(
        f"subscribers: {summary.subscribers_added} added, "
        f"{summary.subscribers_skipped} skipped as already seeded"
    )
    if summary.users_added:
        print(
            "\ntest login accounts (password for all: "
            f"{TEST_USER_PASSWORD}):"
        )
        for user in TEST_USERS:
            print(f"  {user.role.value:8s} {user.phone_number}")


if __name__ == "__main__":
    asyncio.run(main())
