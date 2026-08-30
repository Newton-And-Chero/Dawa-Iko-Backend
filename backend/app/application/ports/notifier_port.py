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
