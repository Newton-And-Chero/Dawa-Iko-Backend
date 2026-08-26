"""Repository port for Subscriber."""

from typing import Protocol
from uuid import UUID

from app.domain.entities.subscriber import Subscriber


class SubscriberRepositoryPort(Protocol):
    async def get_by_id(self, subscriber_id: UUID) -> Subscriber | None: ...

    async def add(self, subscriber: Subscriber) -> Subscriber: ...

    async def update(self, subscriber: Subscriber) -> Subscriber: ...

    async def list_all(self) -> list[Subscriber]: ...
