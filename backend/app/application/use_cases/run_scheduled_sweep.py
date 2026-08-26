"""Scheduled sweep: same resolve -> throttle -> chunk -> dispatch pipeline as
`run_on_demand_sweep`, triggered by Celery Beat for a watchlist commodity x
geography pair (`app/workers/beat_schedule.py`) rather than a human request —
there is no `requester_id`.
"""

from uuid import UUID

from app.application.ports.call_provider_port import CallProviderPort
from app.application.ports.call_repository import CallRepositoryPort
from app.application.ports.commodity_repository import CommodityRepositoryPort
from app.application.ports.geography_resolver_port import GeographyResolverPort
from app.application.ports.realtime_event_bus_port import RealtimeEventBusPort
from app.application.ports.sweep_repository import SweepRepositoryPort
from app.application.use_cases._sweep_dispatch import SweepDependencies, dispatch_sweep
from app.core.config import Settings
from app.domain.enums import CallListIntent, SweepTrigger
from app.domain.value_objects.geography_scope import GeographyScope


class RunScheduledSweepUseCase:
    def __init__(
        self,
        geography_resolver: GeographyResolverPort,
        call_repository: CallRepositoryPort,
        sweep_repository: SweepRepositoryPort,
        commodity_repository: CommodityRepositoryPort,
        call_provider: CallProviderPort,
        settings: Settings,
        realtime_event_bus: RealtimeEventBusPort,
    ) -> None:
        self._deps = SweepDependencies(
            geography_resolver=geography_resolver,
            call_repository=call_repository,
            sweep_repository=sweep_repository,
            commodity_repository=commodity_repository,
            call_provider=call_provider,
            settings=settings,
            realtime_event_bus=realtime_event_bus,
        )

    async def execute(
        self,
        commodity_id: UUID,
        geography: GeographyScope,
        intent: CallListIntent = CallListIntent.PUBLIC_FIRST,
    ) -> UUID:
        return await dispatch_sweep(
            self._deps,
            commodity_id=commodity_id,
            geography=geography,
            trigger_type=SweepTrigger.SCHEDULED,
            requester_id=None,
            intent=intent,
        )
