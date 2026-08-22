"""Repository port for Sweep."""

from typing import Protocol
from uuid import UUID

from app.domain.entities.sweep import Sweep
from app.domain.enums import SweepStatus


class SweepRepositoryPort(Protocol):
    async def get_by_id(self, sweep_id: UUID) -> Sweep | None: ...

    async def add(self, sweep: Sweep) -> Sweep: ...

    async def list_all(self) -> list[Sweep]: ...

    async def update_status(self, sweep_id: UUID, status: SweepStatus) -> None: ...
