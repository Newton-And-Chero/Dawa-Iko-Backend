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

_FAILED_STATUSES = {"failed", "undelivered"}


class TwilioSmsAdapter:
    def __init__(self, settings: Settings, *, http_client: httpx.AsyncClient | None = None) -> None:
        self._account_sid = settings.TWILIO_ACCOUNT_SID
        self._auth_token = settings.TWILIO_AUTH_TOKEN
        self._from_number = settings.TWILIO_FROM_NUMBER
        self._messaging_service_sid = settings.TWILIO_MESSAGING_SERVICE_SID
        self._demo_redirect_numbers = [
            normalize_phone(n) for n in settings.SMS_DEMO_REDIRECT_NUMBERS
        ]
        self._url = f"{_API_BASE_URL}/Accounts/{self._account_sid}/Messages.json"
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
        del metadata

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

    async def _send_one(self, client: httpx.AsyncClient, to: str, body: str) -> str | None:
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
            return f"{to}: {data.get('message', response.text[:200])} (code {data.get('code')})"

        status = data.get("status")
        if status in _FAILED_STATUSES:
            return f"{to}: status {status} ({data.get('error_message') or data.get('error_code')})"
        return None
