"""Repository port for Sweep."""

from typing import TYPE_CHECKING, Protocol
from uuid import UUID

from app.domain.entities.sweep import Sweep
from app.domain.enums import SweepStatus

if TYPE_CHECKING:
    from app.application.use_cases.list_sweeps import SweepFilter


class SweepRepositoryPort(Protocol):
    async def get_by_id(self, sweep_id: UUID) -> Sweep | None: ...

    async def add(self, sweep: Sweep) -> Sweep: ...

    async def list_all(self) -> list[Sweep]: ...

    async def list_by_filter(self, sweep_filter: "SweepFilter") -> list[Sweep]: ...

    async def update_status(self, sweep_id: UUID, status: SweepStatus) -> None: ...
