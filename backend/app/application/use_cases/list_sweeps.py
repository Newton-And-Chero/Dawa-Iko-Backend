"""List/filter sweeps, and fetch one by id — the read side of sweep
management (`RunOnDemandSweepUseCase`/`RunScheduledSweepUseCase` are the
write side)."""

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from app.application.ports.sweep_repository import SweepRepositoryPort
from app.core.exceptions import NotFoundError
from app.domain.entities.sweep import Sweep
from app.domain.enums import SweepStatus


@dataclass
class SweepFilter:
    commodity_id: UUID | None = None
    # Substring match against the sweep's geography_scope (e.g. a county or
    # ward name) — GeographyScope is a tagged union stored as JSONB, so this
    # is a simple text match rather than a scope-kind-aware query.
    geography: str | None = None
    status: SweepStatus | None = None
    date_from: datetime | None = None
    date_to: datetime | None = None


class ListSweepsUseCase:
    def __init__(self, sweep_repository: SweepRepositoryPort) -> None:
        self._sweeps = sweep_repository

    async def execute(self, sweep_filter: SweepFilter | None = None) -> list[Sweep]:
        return await self._sweeps.list_by_filter(sweep_filter or SweepFilter())

    async def get(self, sweep_id: UUID) -> Sweep:
        sweep = await self._sweeps.get_by_id(sweep_id)
        if sweep is None:
            raise NotFoundError(f"sweep {sweep_id} not found")
        return sweep
