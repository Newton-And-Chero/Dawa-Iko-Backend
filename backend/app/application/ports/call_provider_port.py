"""Port for placing and querying calls with the outbound voice provider (CALL-E)."""

from typing import Any, Protocol

from app.domain.value_objects.call_task_ref import CallEventRef, CallRecipient, CallTaskRef


class CallProviderPort(Protocol):
    async def place_call(
        self,
        *,
        task: str,
        recipients: list[CallRecipient],
        result_schema: dict[str, Any] | None,
        recipient_result_schema: dict[str, Any] | None,
        webhook_url: str,
        idempotency_key: str,
        metadata: dict[str, Any] | None = None,
    ) -> CallTaskRef: ...

    async def get_call(self, call_id: str) -> CallTaskRef: ...

    async def list_call_events(self, call_id: str) -> list[CallEventRef]: ...
