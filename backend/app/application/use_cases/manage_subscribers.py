"""Subscriber add/edit — admin-managed (PROJECT.md's data model keeps
Subscriber distinct from User: a subscriber receives alerts, a user logs in;
a person can be both without those being the same row)."""

from dataclasses import dataclass, field
from typing import Any
from uuid import UUID

from app.application.ports.subscriber_repository import SubscriberRepositoryPort
from app.core.exceptions import NotFoundError
from app.domain.entities.subscriber import Subscriber
from app.domain.enums import NotificationChannel


@dataclass
class NewSubscriber:
    name: str
    notification_channel: NotificationChannel
    org: str | None = None
    phone: str | None = None
    email: str | None = None
    webhook_url: str | None = None
    watchlist_commodities: list[UUID] = field(default_factory=list)
    watchlist_geography: dict[str, Any] = field(default_factory=dict)


@dataclass
class SubscriberEdit:
    name: str | None = None
    notification_channel: NotificationChannel | None = None
    org: str | None = None
    phone: str | None = None
    email: str | None = None
    webhook_url: str | None = None
    watchlist_commodities: list[UUID] | None = None
    watchlist_geography: dict[str, Any] | None = None


class ManageSubscribersUseCase:
    def __init__(self, subscriber_repository: SubscriberRepositoryPort) -> None:
        self._subscribers = subscriber_repository

    async def add_subscriber(self, new_subscriber: NewSubscriber) -> Subscriber:
        subscriber = Subscriber(
            name=new_subscriber.name,
            notification_channel=new_subscriber.notification_channel,
            org=new_subscriber.org,
            phone=new_subscriber.phone,
            email=new_subscriber.email,
            webhook_url=new_subscriber.webhook_url,
            watchlist_commodities=list(new_subscriber.watchlist_commodities),
            watchlist_geography=dict(new_subscriber.watchlist_geography),
        )
        return await self._subscribers.add(subscriber)

    async def edit_subscriber(self, subscriber_id: UUID, edit: SubscriberEdit) -> Subscriber:
        subscriber = await self._subscribers.get_by_id(subscriber_id)
        if subscriber is None:
            raise NotFoundError(f"subscriber {subscriber_id} not found")

        if edit.name is not None:
            subscriber.name = edit.name
        if edit.notification_channel is not None:
            subscriber.notification_channel = edit.notification_channel
        if edit.org is not None:
            subscriber.org = edit.org
        if edit.phone is not None:
            subscriber.phone = edit.phone
        if edit.email is not None:
            subscriber.email = edit.email
        if edit.webhook_url is not None:
            subscriber.webhook_url = edit.webhook_url
        if edit.watchlist_commodities is not None:
            subscriber.watchlist_commodities = list(edit.watchlist_commodities)
        if edit.watchlist_geography is not None:
            subscriber.watchlist_geography = dict(edit.watchlist_geography)

        return await self._subscribers.update(subscriber)
