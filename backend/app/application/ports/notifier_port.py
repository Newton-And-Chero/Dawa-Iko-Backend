"""Port for sending one notification (SMS/email/webhook) — the concrete
channel is chosen per `Subscriber.notification_channel`, so every adapter
implements the same `send()` signature regardless of transport."""

from typing import Any, Protocol

from app.domain.enums import NotificationChannel
from app.domain.value_objects.notification_result import NotificationResult


class NotifierPort(Protocol):
    async def send(
        self,
        *,
        channel: NotificationChannel,
        recipient: str,
        message: str,
        metadata: dict[str, Any] | None = None,
    ) -> NotificationResult: ...
