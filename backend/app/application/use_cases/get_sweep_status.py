"""Sweep progress: counts by Call.status for a sweep_id, for polling
(Sprint 05 exposes this over HTTP; Sprint 06 pushes it over WS)."""

from dataclasses import dataclass, field
from uuid import UUID

from app.application.ports.call_repository import CallRepositoryPort
from app.application.ports.sweep_repository import SweepRepositoryPort
from app.core.exceptions import NotFoundError
from app.domain.enums import CallStatus, SweepStatus


@dataclass
class SweepProgress:
    sweep_id: UUID
    status: SweepStatus
    total_calls: int
    counts_by_status: dict[CallStatus, int] = field(default_factory=dict)


class GetSweepStatusUseCase:
    def __init__(
        self, sweep_repository: SweepRepositoryPort, call_repository: CallRepositoryPort
    ) -> None:
        self._sweeps = sweep_repository
        self._calls = call_repository

    async def execute(self, sweep_id: UUID) -> SweepProgress:
        sweep = await self._sweeps.get_by_id(sweep_id)
        if sweep is None:
            raise NotFoundError(f"sweep {sweep_id} not found")

        calls = await self._calls.list_by_sweep_id(sweep_id)
        counts: dict[CallStatus, int] = {}
        for call in calls:
            counts[call.status] = counts.get(call.status, 0) + 1

        return SweepProgress(
            sweep_id=sweep_id,
            status=sweep.status,
            total_calls=len(calls),
            counts_by_status=counts,
        )
