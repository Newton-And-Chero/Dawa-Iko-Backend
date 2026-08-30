from dataclasses import dataclass

from app.domain.enums import NotificationChannel


@dataclass(frozen=True)
class NotificationResult:
    channel: NotificationChannel
    recipient: str
    success: bool
    error: str | None = None
