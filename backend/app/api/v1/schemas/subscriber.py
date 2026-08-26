"""Subscriber response schema — field names mirror the `Subscriber` domain
entity exactly (Sprint 01). Defined now per this sprint's checklist; wired to
a real router with real data in Sprint 07."""

from typing import Any
from uuid import UUID

from pydantic import BaseModel

from app.domain.enums import NotificationChannel


class SubscriberOut(BaseModel):
    id: UUID
    name: str
    org: str | None
    phone: str | None
    email: str | None
    watchlist_commodities: list[UUID]
    watchlist_geography: dict[str, Any]
    notification_channel: NotificationChannel
