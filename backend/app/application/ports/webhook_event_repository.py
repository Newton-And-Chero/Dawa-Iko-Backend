"""Repository port for tracking processed CALL-E webhook event ids.

Backs the "a re-delivery is a no-op, not reprocessed" rule (see workflows/03)
persistently, so a redelivery after a restart is still recognized.
"""

from typing import Protocol


class WebhookEventRepositoryPort(Protocol):
    async def mark_processed(self, event_id: str) -> bool:
        """Record `event_id` as processed. Returns False if it was already recorded."""
        ...
