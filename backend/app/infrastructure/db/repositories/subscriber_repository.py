"""SQLAlchemy implementation of SubscriberRepositoryPort."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.domain.entities.subscriber import Subscriber
from app.infrastructure.db.models import SubscriberModel


def _to_domain(model: SubscriberModel) -> Subscriber:
    return Subscriber(
        id=model.id,
        name=model.name,
        notification_channel=model.notification_channel,
        org=model.org,
        phone=model.phone,
        email=model.email,
        webhook_url=model.webhook_url,
        watchlist_commodities=list(model.watchlist_commodities),
        watchlist_geography=dict(model.watchlist_geography),
    )


def _to_model(subscriber: Subscriber) -> SubscriberModel:
    return SubscriberModel(
        id=subscriber.id,
        name=subscriber.name,
        notification_channel=subscriber.notification_channel,
        org=subscriber.org,
        phone=subscriber.phone,
        email=subscriber.email,
        webhook_url=subscriber.webhook_url,
        watchlist_commodities=list(subscriber.watchlist_commodities),
        watchlist_geography=dict(subscriber.watchlist_geography),
    )


class SqlAlchemySubscriberRepository:
    """Implements SubscriberRepositoryPort."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, subscriber_id: UUID) -> Subscriber | None:
        model = await self._session.get(SubscriberModel, subscriber_id)
        return _to_domain(model) if model is not None else None

    async def add(self, subscriber: Subscriber) -> Subscriber:
        model = _to_model(subscriber)
        self._session.add(model)
        await self._session.commit()
        await self._session.refresh(model)
        return _to_domain(model)

    async def update(self, subscriber: Subscriber) -> Subscriber:
        model = await self._session.get(SubscriberModel, subscriber.id)
        if model is None:
            raise NotFoundError(f"subscriber {subscriber.id} not found")
        updated = _to_model(subscriber)
        for column in SubscriberModel.__table__.columns:
            if column.name == "id":
                continue
            setattr(model, column.name, getattr(updated, column.name))
        await self._session.commit()
        await self._session.refresh(model)
        return _to_domain(model)

    async def list_all(self) -> list[Subscriber]:
        result = await self._session.execute(select(SubscriberModel))
        return [_to_domain(m) for m in result.scalars().all()]
