"""List calls and fetch one by id. No filters in this sprint's checklist —
`GET /calls` is a plain paginated list; `AvailabilityResult` is the filtered,
ranked read path a "where can I get X" view is built from."""

from uuid import UUID

from app.application.ports.call_repository import CallRepositoryPort
from app.core.exceptions import NotFoundError
from app.domain.entities.call import Call


class ListCallsUseCase:
    def __init__(self, call_repository: CallRepositoryPort) -> None:
        self._calls = call_repository

    async def execute(self) -> list[Call]:
        return await self._calls.list_all()

    async def get(self, call_id: UUID) -> Call:
        call = await self._calls.get_by_id(call_id)
        if call is None:
            raise NotFoundError(f"call {call_id} not found")
        return call
