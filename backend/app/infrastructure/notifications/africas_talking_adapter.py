"""AfricasTalkingAdapter — real SMS delivery via Africa's Talking's REST API,
called directly with httpx rather than the `africastalking` package (RULES.md:
one fewer dependency, same wire contract). Selected only when
`Settings.SMS_MODE=live`; never invoked by an automated test (RULES.md: no
test calls a real paid API)."""

import logging
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


class AfricasTalkingAdapter:
    """Implements NotifierPort."""

    def __init__(self, settings: Settings) -> None:
        self._username = settings.AFRICAS_TALKING_USERNAME
        self._api_key = settings.AFRICAS_TALKING_API_KEY
        self._sender_id = settings.AFRICAS_TALKING_SENDER_ID
        self._base_url = _SANDBOX_BASE_URL if self._username == "sandbox" else _LIVE_BASE_URL

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
        async with httpx.AsyncClient(timeout=10.0) as client:
            try:
                response = await client.post(self._base_url, data=payload, headers=headers)
                response.raise_for_status()
            except httpx.HTTPError as exc:
                logger.warning("Africa's Talking SMS to %s failed: %s", recipient, exc)
                return NotificationResult(
                    channel=channel, recipient=recipient, success=False, error=str(exc)
                )
        return NotificationResult(channel=channel, recipient=recipient, success=True)
