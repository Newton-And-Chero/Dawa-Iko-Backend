"""Seed the database for a demo: facilities + commodities (Sprint 02's
seed_db.py), then several historical weekly sweeps per watchlist commodity so
Sprint 08's stockout-rate-over-time view has real (mock-sourced) data before
any demo (PROJECT.md MVP item 7).

Every sweep here runs against `MockCallEAdapter` — no real phone calls, ever
(RULES.md). The webhook fires through the real ASGI app/route exactly as a
live CALL-E delivery would, then each sweep's `Sweep.created_at`/
`Call.started_at`/`Call.ended_at` are backdated directly against the ORM
models (there is no repository method for this — SweepRepositoryPort has no
`update_created_at`, and adding one solely for this script would be a
premature abstraction) so the historical spread is real rows, not a
fabricated read-time illusion.

Usage: uv run python -m scripts.seed_demo
"""

import asyncio
from datetime import UTC, datetime, timedelta
from uuid import UUID

from httpx import ASGITransport, AsyncClient
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.use_cases.run_on_demand_sweep import RunOnDemandSweepUseCase
from app.core.config import Settings, get_settings
from app.domain.enums import SweepStatus
from app.domain.value_objects.geography_scope import CountyScope
from app.infrastructure.cache.redis import get_redis
from app.infrastructure.call_e.mock_calle_adapter import MockCallEAdapter
from app.infrastructure.db.models import CallModel, SweepModel
from app.infrastructure.db.repositories.call_repository import SqlAlchemyCallRepository
from app.infrastructure.db.repositories.commodity_repository import SqlAlchemyCommodityRepository
from app.infrastructure.db.repositories.sweep_repository import SqlAlchemySweepRepository
from app.infrastructure.db.session import async_session_factory
from app.infrastructure.geo.postgis_geography_resolver import PostGISGeographyResolver
from app.infrastructure.realtime.event_bus import RealtimeEventBus
from app.main import app
from app.workers.beat_schedule import WATCHLIST_SWEEPS
from scripts.seed_db import TEST_USER_PASSWORD, TEST_USERS, run_seed

# How many past weeks of sweep history to backfill per watchlist commodity —
# matches compute_stockout_analytics.py's own `_SUMMARY_WINDOW`, so the
# "unavailable for N of the last 8 weeks" line has all 8 weeks to draw on.
HISTORY_WEEKS = 8


async def _run_one_backdated_sweep(
    *,
    http_client: AsyncClient,
    commodity_id: UUID,
    county: str,
    backdated_at: datetime,
    seed: int,
) -> int:
    """Runs one on-demand sweep against every facility in `county`, waits for
    every mock webhook to land, then backdates the sweep + its calls to
    `backdated_at`. Returns the number of facilities called.
    """
    settings = Settings(
        MAX_RECIPIENTS_PER_TASK=get_settings().MAX_RECIPIENTS_PER_TASK,
        # Real sweeps never re-call a facility within a week (RULES.md
        # pharmacy-fatigue rule) — that would block every week but the
        # first when backfilling history in a tight loop, so it's disabled
        # for this script only.
        FACILITY_CALL_COOLDOWN_HOURS=0,
    )
    # A short delay risks the webhook firing before dispatch_call_chunk's own
    # bulk_update commits provider_call_id onto the Call rows it just
    # created — under real Postgres latency (unlike the fast local sqlite-ish
    # round trips the test suite sees), that race lands often enough with a
    # 50-facility chunk to make the webhook 409 as an "unknown call" and
    # strand the sweep at in_progress forever. A generous delay avoids it.
    adapter = MockCallEAdapter(http_client=http_client, webhook_delay_seconds=1.5, seed=seed)

    async with async_session_factory() as session:
        use_case = RunOnDemandSweepUseCase(
            geography_resolver=PostGISGeographyResolver(session),
            call_repository=SqlAlchemyCallRepository(session),
            sweep_repository=SqlAlchemySweepRepository(session),
            commodity_repository=SqlAlchemyCommodityRepository(session),
            call_provider=adapter,
            settings=settings,
            realtime_event_bus=RealtimeEventBus(get_redis()),
        )
        sweep_id = await use_case.execute(
            commodity_id=commodity_id, geography=CountyScope(county=county)
        )

        calls = await SqlAlchemyCallRepository(session).list_by_sweep_id(sweep_id)
        for call in calls:
            if call.provider_call_id is not None:
                await adapter.wait_for_webhook(call.provider_call_id)

    async with async_session_factory() as session:
        sweep = await SqlAlchemySweepRepository(session).get_by_id(sweep_id)
        if sweep is not None and sweep.status != SweepStatus.COMPLETED:
            print(
                f"  warning: sweep {sweep_id} is {sweep.status.value}, not completed — "
                "some webhooks may not have landed"
            )

        await session.execute(
            update(SweepModel).where(SweepModel.id == sweep_id).values(created_at=backdated_at)
        )
        await session.execute(
            update(CallModel)
            .where(CallModel.sweep_id == sweep_id)
            .values(started_at=backdated_at, ended_at=backdated_at)
        )
        await session.commit()

    return len(calls)


async def _seed_sweep_history(session: AsyncSession) -> None:
    commodities = await SqlAlchemyCommodityRepository(session).list_all()
    by_keml_code = {c.keml_code: c for c in commodities if c.keml_code}

    now = datetime.now(UTC)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as http_client:
        for keml_code, county in WATCHLIST_SWEEPS:
            commodity = by_keml_code.get(keml_code)
            if commodity is None:
                print(f"skipping {keml_code}/{county}: no seeded commodity with that keml_code")
                continue

            print(f"backfilling {HISTORY_WEEKS} weeks of {commodity.name} sweeps in {county}...")
            for week_offset in range(HISTORY_WEEKS - 1, -1, -1):
                backdated_at = now - timedelta(weeks=week_offset)
                called = await _run_one_backdated_sweep(
                    http_client=http_client,
                    commodity_id=commodity.id,
                    county=county,
                    backdated_at=backdated_at,
                    seed=week_offset + hash((keml_code, county)) % 1000,
                )
                print(f"  week -{week_offset}: {called} facilities called")


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
        print(f"\ntest login accounts (password for all: {TEST_USER_PASSWORD}):")
        for user in TEST_USERS:
            print(f"  {user.role.value:8s} {user.phone_number}")

    async with async_session_factory() as session:
        await _seed_sweep_history(session)

    print("done — historical sweep data is in place for the time-series view.")


if __name__ == "__main__":
    asyncio.run(main())
