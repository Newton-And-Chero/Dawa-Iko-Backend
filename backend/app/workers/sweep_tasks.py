"""Celery tasks wrapping the Beat-triggered sweep-orchestration use cases.

Only the recurring flows run as Celery tasks. The on-demand flow
(`RunOnDemandSweepUseCase`) is called directly by Sprint 05's HTTP routers
per this sprint's fixed internal contract — it is not queued, since it must
return a `sweep_id` synchronously to the caller.
"""

import asyncio

from app.application.use_cases.retry_failed_calls import RetryFailedCallsUseCase
from app.application.use_cases.run_scheduled_sweep import RunScheduledSweepUseCase
from app.core.config import get_settings
from app.core.exceptions import NotFoundError
from app.domain.value_objects.geography_scope import CountyScope
from app.infrastructure.cache.redis import get_redis
from app.infrastructure.call_e.factory import build_call_provider
from app.infrastructure.db.repositories.call_repository import SqlAlchemyCallRepository
from app.infrastructure.db.repositories.commodity_repository import SqlAlchemyCommodityRepository
from app.infrastructure.db.repositories.facility_repository import SqlAlchemyFacilityRepository
from app.infrastructure.db.repositories.sweep_repository import SqlAlchemySweepRepository
from app.infrastructure.db.session import async_session_factory
from app.infrastructure.geo.postgis_geography_resolver import PostGISGeographyResolver
from app.infrastructure.realtime.event_bus import RealtimeEventBus
from app.workers.celery_app import celery_app


async def _run_scheduled_sweep(commodity_keml_code: str, county: str) -> None:
    settings = get_settings()
    async with async_session_factory() as session:
        commodity_repository = SqlAlchemyCommodityRepository(session)
        commodities = await commodity_repository.list_all()
        commodity = next((c for c in commodities if c.keml_code == commodity_keml_code), None)
        if commodity is None:
            raise NotFoundError(f"no commodity seeded with keml_code {commodity_keml_code!r}")

        use_case = RunScheduledSweepUseCase(
            geography_resolver=PostGISGeographyResolver(session),
            call_repository=SqlAlchemyCallRepository(session),
            sweep_repository=SqlAlchemySweepRepository(session),
            commodity_repository=commodity_repository,
            call_provider=build_call_provider(settings),
            settings=settings,
            realtime_event_bus=RealtimeEventBus(get_redis()),
        )
        await use_case.execute(commodity_id=commodity.id, geography=CountyScope(county=county))


@celery_app.task(name="app.workers.sweep_tasks.run_scheduled_sweep_task")  # type: ignore[untyped-decorator]
def run_scheduled_sweep_task(commodity_keml_code: str, county: str) -> None:
    asyncio.run(_run_scheduled_sweep(commodity_keml_code, county))


async def _retry_failed_calls() -> None:
    settings = get_settings()
    async with async_session_factory() as session:
        use_case = RetryFailedCallsUseCase(
            call_repository=SqlAlchemyCallRepository(session),
            facility_repository=SqlAlchemyFacilityRepository(session),
            sweep_repository=SqlAlchemySweepRepository(session),
            commodity_repository=SqlAlchemyCommodityRepository(session),
            call_provider=build_call_provider(settings),
            settings=settings,
        )
        await use_case.execute()


@celery_app.task(name="app.workers.sweep_tasks.retry_failed_calls_task")  # type: ignore[untyped-decorator]
def retry_failed_calls_task() -> None:
    asyncio.run(_retry_failed_calls())
