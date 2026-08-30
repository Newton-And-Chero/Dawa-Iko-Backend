from uuid import UUID

from app.application.ports.subscriber_repository import SubscriberRepositoryPort
from app.core.exceptions import NotFoundError
from app.domain.entities.subscriber import Subscriber


class ListSubscribersUseCase:
    def __init__(self, subscriber_repository: SubscriberRepositoryPort) -> None:
        self._subscribers = subscriber_repository

    async def execute(self) -> list[Subscriber]:
        return await self._subscribers.list_all()

    async def get(self, subscriber_id: UUID) -> Subscriber:
        subscriber = await self._subscribers.get_by_id(subscriber_id)
        if subscriber is None:
            raise NotFoundError(f"subscriber {subscriber_id} not found")
        return subscriber
