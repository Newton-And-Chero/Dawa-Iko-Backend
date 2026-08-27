"""AfricasTalkingAdapter — real SMS delivery via Africa's Talking's REST API,
called directly with httpx rather than the `africastalking` package (RULES.md:
one fewer dependency, same wire contract). Selected only when
`Settings.SMS_MODE=live`; never invoked by an automated test (RULES.md: no
test calls a real paid API)."""

import contextlib
import logging
from collections.abc import AsyncIterator
from typing import Any

import httpx

from app.core.config import Settings
from app.domain.enums import NotificationChannel
from app.domain.value_objects.notification_result import NotificationResult

logger = logging.getLogger(__name__)

# Africa's Talking routes the sandbox username to a separate host from
# production — see docs.africastalking.com.
_SANDBOX_BASE_URL = "https://api.sandbox.africastalking.com/version1/messaging"
_LIVE_BASE_URL = "https://api.africastalking.com/version1/messaging"

# Per-recipient statusCode values that mean the message was accepted for
# delivery (docs.africastalking.com/sms/statuscodes). Anything else — invalid
# number, blacklist, insufficient balance, gateway rejection — is a failure
# even though the HTTP response is still 201.
_ACCEPTED_STATUS_CODES = {100, 101, 102}


class AfricasTalkingAdapter:
    """Implements NotifierPort."""

    def __init__(
        self, settings: Settings, *, http_client: httpx.AsyncClient | None = None
    ) -> None:
        self._username = settings.AFRICAS_TALKING_USERNAME
        self._api_key = settings.AFRICAS_TALKING_API_KEY
        self._sender_id = settings.AFRICAS_TALKING_SENDER_ID
        self._base_url = _SANDBOX_BASE_URL if self._username == "sandbox" else _LIVE_BASE_URL
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
        del metadata  # not part of Africa's Talking's SMS payload
        payload = {"username": self._username, "to": recipient, "message": message}
        if self._sender_id:
            payload["from"] = self._sender_id
        headers = {
            "apiKey": self._api_key,
            "Content-Type": "application/x-www-form-urlencoded",
            "Accept": "application/json",
        }
        async with self._client() as client:
            try:
                response = await client.post(self._base_url, data=payload, headers=headers)
                response.raise_for_status()
            except httpx.HTTPError as exc:
                logger.warning("Africa's Talking SMS to %s failed: %s", recipient, exc)
                return NotificationResult(
                    channel=channel, recipient=recipient, success=False, error=str(exc)
                )

        # A 2xx only means Africa's Talking accepted the request — per-recipient
        # outcome (bad number, blacklist, no balance) lives in the body.
        error = self._recipient_error(response)
        if error is not None:
            logger.warning("Africa's Talking SMS to %s rejected: %s", recipient, error)
            return NotificationResult(
                channel=channel, recipient=recipient, success=False, error=error
            )
        return NotificationResult(channel=channel, recipient=recipient, success=True)

    @staticmethod
    def _recipient_error(response: httpx.Response) -> str | None:
        """Return a failure reason if the body reports the recipient was not
        accepted, or ``None`` if it was."""
        try:
            recipients = response.json()["SMSMessageData"]["Recipients"]
        except (ValueError, KeyError, TypeError):
            return f"unparseable Africa's Talking response: {response.text[:200]}"
        if not recipients:
            # e.g. "Sent to 0/1 Total Cost: KES 0" — nothing was queued.
            return "Africa's Talking accepted no recipients"
        entry = recipients[0]
        if entry.get("statusCode") in _ACCEPTED_STATUS_CODES:
            return None
        return (
            f"status {entry.get('status', 'unknown')} "
            f"(code {entry.get('statusCode', 'unknown')})"
        )
