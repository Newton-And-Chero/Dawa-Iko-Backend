"""Repository port for AvailabilityResult."""

from typing import TYPE_CHECKING, Protocol
from uuid import UUID

from app.domain.entities.availability_result import AvailabilityResult

if TYPE_CHECKING:
    from app.application.use_cases.list_availability_results import AvailabilityResultFilter


class AvailabilityResultRepositoryPort(Protocol):
    async def get_by_id(self, availability_result_id: UUID) -> AvailabilityResult | None: ...

    async def get_by_call_id(self, call_id: UUID) -> AvailabilityResult | None: ...

    async def add(self, availability_result: AvailabilityResult) -> AvailabilityResult: ...

    async def update(self, availability_result: AvailabilityResult) -> AvailabilityResult: ...

    async def list_all(self) -> list[AvailabilityResult]: ...

    async def list_by_filter(
        self, result_filter: "AvailabilityResultFilter"
    ) -> list[AvailabilityResult]: ...
