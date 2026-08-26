"""Subscriber entity."""

from dataclasses import dataclass, field
from typing import Any
from uuid import UUID, uuid4

from app.domain.enums import NotificationChannel


@dataclass
class Subscriber:
    name: str
    notification_channel: NotificationChannel
    id: UUID = field(default_factory=uuid4)
    org: str | None = None
    phone: str | None = None
    email: str | None = None
    # Populated when notification_channel is WEBHOOK — WebhookNotifier POSTs
    # alerts here.
    webhook_url: str | None = None
    watchlist_commodities: list[UUID] = field(default_factory=list)
    watchlist_geography: dict[str, Any] = field(default_factory=dict)
