"""Celery task wrapping the scheduled facility-reliability recompute
(workflows/08: never computed synchronously inside the webhook/call-handling
path). Mirrors `sweep_tasks.py`'s own session-per-run pattern."""

import asyncio

from app.application.use_cases.compute_facility_reliability import (
    ComputeFacilityReliabilityUseCase,
)
from app.infrastructure.db.repositories.analytics_repository import SqlAlchemyAnalyticsRepository
from app.infrastructure.db.repositories.facility_repository import SqlAlchemyFacilityRepository
from app.infrastructure.db.session import async_session_factory
from app.workers.celery_app import celery_app


async def _recompute_facility_reliability() -> None:
    async with async_session_factory() as session:
        use_case = ComputeFacilityReliabilityUseCase(
            analytics_repository=SqlAlchemyAnalyticsRepository(session),
            facility_repository=SqlAlchemyFacilityRepository(session),
        )
        await use_case.recompute_and_persist_all()


@celery_app.task(  # type: ignore[untyped-decorator]
    name="app.workers.analytics_tasks.recompute_facility_reliability_task"
)
def recompute_facility_reliability_task() -> None:
    asyncio.run(_recompute_facility_reliability())
