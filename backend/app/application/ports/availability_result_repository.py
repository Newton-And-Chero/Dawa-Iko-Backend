"""Repository port for AvailabilityResult."""

from typing import Protocol
from uuid import UUID

from app.domain.entities.availability_result import AvailabilityResult


class AvailabilityResultRepositoryPort(Protocol):
    async def get_by_id(self, availability_result_id: UUID) -> AvailabilityResult | None: ...

    async def get_by_call_id(self, call_id: UUID) -> AvailabilityResult | None: ...

    async def add(self, availability_result: AvailabilityResult) -> AvailabilityResult: ...

    async def update(self, availability_result: AvailabilityResult) -> AvailabilityResult: ...

    async def list_all(self) -> list[AvailabilityResult]: ...
