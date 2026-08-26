"""Manual "call this facility now" — e.g. reconfirming a hold before a
patient travels there. Single-facility, immediate, bypasses sweep grouping
(resolve/prioritize/chunk never run) but still creates a minimal one-facility
Sweep, since every Call belongs to one.

This is the one documented, explicit cooldown bypass (PROJECT.md 2.2): a
human deliberately asked for this specific call, so `is_cooldown_blocked` is
never consulted here. It must stay a single, narrow use case — not a general
escape hatch the sweep engine reaches for on its own.
"""

from uuid import UUID

from app.application.ports.call_provider_port import CallProviderPort
from app.application.ports.call_repository import CallRepositoryPort
from app.application.ports.commodity_repository import CommodityRepositoryPort
from app.application.ports.facility_repository import FacilityRepositoryPort
from app.application.ports.realtime_event_bus_port import RealtimeEventBusPort
from app.application.ports.sweep_repository import SweepRepositoryPort
from app.application.realtime_events import publish_sweep_status_event
from app.application.use_cases._sweep_dispatch import dispatch_call_chunk
from app.core.exceptions import NotFoundError
from app.domain.entities.sweep import Sweep
from app.domain.enums import SweepStatus, SweepTrigger


class RequestManualCallUseCase:
    def __init__(
        self,
        call_repository: CallRepositoryPort,
        facility_repository: FacilityRepositoryPort,
        sweep_repository: SweepRepositoryPort,
        commodity_repository: CommodityRepositoryPort,
        call_provider: CallProviderPort,
        realtime_event_bus: RealtimeEventBusPort,
    ) -> None:
        self._calls = call_repository
        self._facilities = facility_repository
        self._sweeps = sweep_repository
        self._commodities = commodity_repository
        self._call_provider = call_provider
        self._realtime_event_bus = realtime_event_bus

    async def execute(
        self, facility_id: UUID, commodity_id: UUID, requester_id: UUID | None = None
    ) -> UUID:
        facility = await self._facilities.get_by_id(facility_id)
        if facility is None:
            raise NotFoundError(f"facility {facility_id} not found")
        commodity = await self._commodities.get_by_id(commodity_id)
        if commodity is None:
            raise NotFoundError(f"commodity {commodity_id} not found")

        sweep = await self._sweeps.add(
            Sweep(
                commodity_id=commodity_id,
                geography_scope={"kind": "manual_facility", "facility_id": str(facility_id)},
                trigger_type=SweepTrigger.ON_DEMAND,
                status=SweepStatus.QUEUED,
                requester_id=requester_id,
            )
        )

        await dispatch_call_chunk(
            self._calls,
            self._call_provider,
            commodity_name=commodity.name,
            facilities=[facility],
            sweep_id=sweep.id,
            idempotency_key=f"{sweep.id}:manual",
            attempt_number=1,
        )
        await self._sweeps.update_status(sweep.id, SweepStatus.IN_PROGRESS)
        await publish_sweep_status_event(
            self._realtime_event_bus, self._sweeps, self._calls, sweep.id
        )
        return sweep.id

    async def execute_from_call(self, call_id: UUID, requester_id: UUID | None = None) -> UUID:
        """`POST /calls/{call_id}/retry` — re-derive the facility/commodity a
        past `Call` was for, and place a fresh manual call for the same pair."""
        call = await self._calls.get_by_id(call_id)
        if call is None:
            raise NotFoundError(f"call {call_id} not found")
        sweep = await self._sweeps.get_by_id(call.sweep_id)
        if sweep is None:
            raise NotFoundError(f"sweep {call.sweep_id} not found")
        return await self.execute(
            facility_id=call.facility_id,
            commodity_id=sweep.commodity_id,
            requester_id=requester_id,
        )
