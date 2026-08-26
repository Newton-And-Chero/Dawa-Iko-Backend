"""EmailNotifier — simple SMTP delivery for subscribers with
notification_channel=email. Mirrors the mock/live split every other
real-world-side-effect adapter uses (RULES.md): `Settings.EMAIL_MODE=mock`
(the default) logs instead of sending; `live` sends via SMTP."""

import asyncio
import logging
import smtplib
from email.message import EmailMessage
from typing import Any

from app.core.config import Settings
from app.domain.enums import NotificationChannel
from app.domain.value_objects.notification_result import NotificationResult

logger = logging.getLogger(__name__)


class EmailNotifier:
    """Implements NotifierPort."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    async def send(
        self,
        *,
        channel: NotificationChannel,
        recipient: str,
        message: str,
        metadata: dict[str, Any] | None = None,
    ) -> NotificationResult:
        del metadata
        if self._settings.EMAIL_MODE == "mock":
            logger.info("mock email -> %s: %s", recipient, message)
            return NotificationResult(channel=channel, recipient=recipient, success=True)

        try:
            await asyncio.to_thread(self._send_smtp, recipient, message)
        except (OSError, smtplib.SMTPException) as exc:
            logger.warning("email to %s failed: %s", recipient, exc)
            return NotificationResult(
                channel=channel, recipient=recipient, success=False, error=str(exc)
            )
        return NotificationResult(channel=channel, recipient=recipient, success=True)

    def _send_smtp(self, recipient: str, message: str) -> None:
        email_message = EmailMessage()
        email_message["Subject"] = "CALL-E stockout alert"
        email_message["From"] = self._settings.SMTP_FROM_ADDRESS
        email_message["To"] = recipient
        email_message.set_content(message)
        with smtplib.SMTP(self._settings.SMTP_HOST, self._settings.SMTP_PORT, timeout=10) as smtp:
            smtp.starttls()
            if self._settings.SMTP_USERNAME:
                smtp.login(self._settings.SMTP_USERNAME, self._settings.SMTP_PASSWORD)
            smtp.send_message(email_message)
