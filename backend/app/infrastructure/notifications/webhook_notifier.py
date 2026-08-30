import asyncio
import logging
from typing import Any

import httpx

from app.domain.enums import NotificationChannel
from app.domain.value_objects.notification_result import NotificationResult

logger = logging.getLogger(__name__)

_MAX_ATTEMPTS = 3
_BASE_BACKOFF_SECONDS = 0.5


class WebhookNotifier:
    def __init__(
        self, *, http_client: httpx.AsyncClient | None = None, timeout: float = 5.0
    ) -> None:
        self._http_client = http_client
        self._timeout = timeout

    async def send(
        self,
        *,
        channel: NotificationChannel,
        recipient: str,
        message: str,
        metadata: dict[str, Any] | None = None,
    ) -> NotificationResult:
        payload = {"message": message, "metadata": metadata or {}}
        owns_client = self._http_client is None
        client = self._http_client or httpx.AsyncClient(timeout=self._timeout)
        try:
            return await self._send_with_retries(client, channel, recipient, payload)
        finally:
            if owns_client:
                await client.aclose()

    async def _send_with_retries(
        self,
        client: httpx.AsyncClient,
        channel: NotificationChannel,
        recipient: str,
        payload: dict[str, Any],
    ) -> NotificationResult:
        last_error: str | None = None
        for attempt in range(1, _MAX_ATTEMPTS + 1):
            try:
                response = await client.post(recipient, json=payload)
                response.raise_for_status()
                return NotificationResult(channel=channel, recipient=recipient, success=True)
            except httpx.HTTPError as exc:
                last_error = str(exc)
                if attempt < _MAX_ATTEMPTS:
                    await asyncio.sleep(_BASE_BACKOFF_SECONDS * attempt)
        logger.warning(
            "webhook delivery to %s failed after %d attempts: %s",
            recipient,
            _MAX_ATTEMPTS,
            last_error,
        )
        return NotificationResult(
            channel=channel, recipient=recipient, success=False, error=last_error
        )
