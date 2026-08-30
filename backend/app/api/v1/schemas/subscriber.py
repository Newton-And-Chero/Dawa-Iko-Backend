from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field

from app.domain.enums import NotificationChannel


class SubscriberIn(BaseModel):
    name: str
    notification_channel: NotificationChannel
    org: str | None = None
    phone: str | None = None
    email: str | None = None
    webhook_url: str | None = None
    watchlist_commodities: list[UUID] = Field(default_factory=list)
    watchlist_geography: dict[str, Any] = Field(default_factory=dict)


class SubscriberEditIn(BaseModel):
    name: str | None = None
    notification_channel: NotificationChannel | None = None
    org: str | None = None
    phone: str | None = None
    email: str | None = None
    webhook_url: str | None = None
    watchlist_commodities: list[UUID] | None = None
    watchlist_geography: dict[str, Any] | None = None


class SubscriberOut(BaseModel):
    id: UUID
    name: str
    org: str | None
    phone: str | None
    email: str | None
    webhook_url: str | None
    watchlist_commodities: list[UUID]
    watchlist_geography: dict[str, Any]
    notification_channel: NotificationChannel
