from typing import Protocol


class WebhookEventRepositoryPort(Protocol):
    async def was_processed(self, event_id: str) -> bool: ...

    async def mark_processed(self, event_id: str) -> bool: ...
