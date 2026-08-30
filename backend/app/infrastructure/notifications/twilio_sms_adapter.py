"""TwilioSmsAdapter — real SMS delivery via Twilio's REST API, called directly
with httpx rather than the `twilio` package (RULES.md: one fewer dependency,
same wire contract). Selected only when `Settings.SMS_MODE=live`; never invoked
by an automated test (RULES.md: no test calls a real paid API).

Hackathon guardrail: when `Settings.SMS_DEMO_REDIRECT_NUMBERS` is non-empty no
real subscriber number is ever texted — every message is delivered to every
number in that list instead (a Twilio trial account can only send to its own
verified numbers). This mirrors `CALL_DEMO_REDIRECT_NUMBERS` on the call path.
"""

import contextlib
import logging
from collections.abc import AsyncIterator
from typing import Any

import httpx

from app.core.config import Settings
from app.domain.enums import NotificationChannel
from app.domain.services.phone import normalize_phone
from app.domain.value_objects.notification_result import NotificationResult

logger = logging.getLogger(__name__)

_API_BASE_URL = "https://api.twilio.com/2010-04-01"

# Twilio Message.status values at send time that mean the message was accepted
# for delivery (www.twilio.com/docs/messaging/api/message-resource#message-status-values).
# "failed"/"undelivered" are terminal failures; anything else is still in flight
# and counts as accepted here (final state arrives via a status callback we
# don't wire up in this project).
_FAILED_STATUSES = {"failed", "undelivered"}


class TwilioSmsAdapter:
    """Implements NotifierPort."""

    def __init__(
        self, settings: Settings, *, http_client: httpx.AsyncClient | None = None
    ) -> None:
        self._account_sid = settings.TWILIO_ACCOUNT_SID
        self._auth_token = settings.TWILIO_AUTH_TOKEN
        self._from_number = settings.TWILIO_FROM_NUMBER
        self._messaging_service_sid = settings.TWILIO_MESSAGING_SERVICE_SID
        self._demo_redirect_numbers = [
            normalize_phone(n) for n in settings.SMS_DEMO_REDIRECT_NUMBERS
        ]
        self._url = f"{_API_BASE_URL}/Accounts/{self._account_sid}/Messages.json"
        # Injected only by tests; production opens a fresh client per send.
        self._http_client = http_client

    @contextlib.asynccontextmanager
    async def _client(self) -> AsyncIterator[httpx.AsyncClient]:
        if self._http_client is not None:
            yield self._http_client
            return
        async with httpx.AsyncClient(timeout=10.0) as client:
            yield client

    async def send(
        self,
        *,
        channel: NotificationChannel,
        recipient: str,
        message: str,
        metadata: dict[str, Any] | None = None,
    ) -> NotificationResult:
        del metadata  # not part of Twilio's SMS payload

        if self._demo_redirect_numbers:
            targets = self._demo_redirect_numbers
            body = f"[for {recipient}] {message}"
            logger.info(
                "SMS_DEMO_REDIRECT_NUMBERS active: message for %s redirected to %d demo number(s)",
                recipient,
                len(targets),
            )
        else:
            targets = [recipient]
            body = message

        async with self._client() as client:
            errors = [
                error
                for target in targets
                if (error := await self._send_one(client, target, body)) is not None
            ]

        if errors:
            joined = "; ".join(errors)
            logger.warning("Twilio SMS for %s failed: %s", recipient, joined)
            return NotificationResult(
                channel=channel, recipient=recipient, success=False, error=joined
            )
        return NotificationResult(channel=channel, recipient=recipient, success=True)

    async def _send_one(
        self, client: httpx.AsyncClient, to: str, body: str
    ) -> str | None:
        """POST one message; return a failure reason or ``None`` on acceptance."""
        payload = {"To": to, "Body": body}
        if self._messaging_service_sid:
            payload["MessagingServiceSid"] = self._messaging_service_sid
        else:
            payload["From"] = self._from_number

        try:
            response = await client.post(
                self._url, data=payload, auth=(self._account_sid, self._auth_token)
            )
        except httpx.HTTPError as exc:
            return f"{to}: {exc}"

        try:
            data = response.json()
        except ValueError:
            return f"{to}: unparseable Twilio response ({response.text[:200]})"

        if response.status_code >= 400:
            # Twilio error body: {"code": 21211, "message": "...", "more_info": ...}
            return f"{to}: {data.get('message', response.text[:200])} (code {data.get('code')})"

        status = data.get("status")
        if status in _FAILED_STATUSES:
            return f"{to}: status {status} ({data.get('error_message') or data.get('error_code')})"
        return None
