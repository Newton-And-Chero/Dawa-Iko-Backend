"""MockSMSAdapter — implements NotifierPort by logging instead of sending.
Selected via `Settings.SMS_MODE=mock` (default everywhere except an explicit
production-like environment, per RULES.md). Records every send in `.sent`
for test assertions."""

import logging
from typing import Any

from app.domain.enums import NotificationChannel
from app.domain.value_objects.notification_result import NotificationResult

logger = logging.getLogger(__name__)


class MockSMSAdapter:
    """Implements NotifierPort. Zero real SMS is ever sent."""

    def __init__(self) -> None:
        self.sent: list[dict[str, Any]] = []

    async def send(
        self,
        *,
        channel: NotificationChannel,
        recipient: str,
        message: str,
        metadata: dict[str, Any] | None = None,
    ) -> NotificationResult:
        logger.info("mock sms -> %s: %s", recipient, message)
        self.sent.append(
            {"channel": channel, "recipient": recipient, "message": message, "metadata": metadata}
        )
        return NotificationResult(channel=channel, recipient=recipient, success=True)
