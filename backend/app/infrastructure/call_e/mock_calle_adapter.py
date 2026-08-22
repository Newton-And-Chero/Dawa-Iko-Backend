"""MockCallEAdapter — simulates CALL-E in-process. No network calls to CALL-E, ever.

`place_call` generates a plausible, clearly-synthetic `CallTaskRef` and then
fires the *same* webhook POST a real CALL-E delivery would send — via a real
HTTP request through the injected `httpx.AsyncClient` — so the webhook route
and `handle_calle_webhook` are exercised end-to-end, not bypassed. The fire
is deferred a short delay so a caller has time to persist `provider_call_id`
onto its `Call` rows (from the returned `CallTaskRef`) before the webhook
lands, exactly as a real dispatch-then-webhook flow would.
"""

import asyncio
import random
import secrets
from datetime import UTC, datetime
from typing import Any

import httpx

from app.core.exceptions import NotFoundError
from app.domain.value_objects.call_task_ref import (
    CallAttemptRef,
    CallEventRef,
    CallRecipient,
    CallRecipientResultRef,
    CallTaskRef,
    CompletionConfidenceRef,
    TranscriptTurnRef,
)

_SYNTHETIC_NOTE = "Synthetic mock result (MockCallEAdapter) — not a real call."
_QUANTITY_BANDS = ["low", "medium", "high"]


def _simulate_recipient(rng: random.Random) -> tuple[str, dict[str, Any] | None, str | None]:
    """Returns (recipient_status, structured_result, failure_code)."""
    roll = rng.random()
    if roll < 0.10:
        return "failed", None, "no_answer"
    if roll < 0.15:
        return (
            "completed",
            {
                "in_stock": "unknown",
                "quantity_band": None,
                "price_kes": None,
                "last_restock_date": None,
                "can_hold": None,
                "hold_duration_hours": None,
                "notes": f"{_SYNTHETIC_NOTE} Respondent was unsure.",
            },
            None,
        )
    if roll < 0.55:
        return (
            "completed",
            {
                "in_stock": "yes",
                "quantity_band": rng.choice(_QUANTITY_BANDS),
                "price_kes": round(rng.uniform(50, 2000), 2),
                "last_restock_date": None,
                "can_hold": rng.random() < 0.6,
                "hold_duration_hours": rng.choice([4, 24, 48]) if rng.random() < 0.6 else None,
                "notes": _SYNTHETIC_NOTE,
            },
            None,
        )
    return (
        "completed",
        {
            "in_stock": "no",
            "quantity_band": None,
            "price_kes": None,
            "last_restock_date": "2026-07-01" if rng.random() < 0.5 else None,
            "can_hold": None,
            "hold_duration_hours": None,
            "notes": _SYNTHETIC_NOTE,
        },
        None,
    )


def _attempt_to_dict(attempt: CallAttemptRef) -> dict[str, Any]:
    return {
        "id": attempt.id,
        "phone": attempt.phone,
        "status": attempt.status,
        "started_at": attempt.started_at.isoformat() if attempt.started_at else None,
        "completed_at": attempt.completed_at.isoformat() if attempt.completed_at else None,
        "summary": attempt.summary,
        "transcript_turns": [
            {"offset_seconds": t.offset_seconds, "speaker": t.speaker, "text": t.text}
            for t in attempt.transcript_turns
        ],
        "provider_call_id": attempt.provider_call_id,
        "failure_code": attempt.failure_code,
        "failure_message": attempt.failure_message,
    }


def _recipient_to_dict(recipient: CallRecipientResultRef) -> dict[str, Any]:
    return {
        "id": recipient.id,
        "phones": recipient.phones,
        "status": recipient.status,
        "structured_result": recipient.structured_result,
        "summary": recipient.summary,
        "attempts": [_attempt_to_dict(a) for a in recipient.attempts],
    }


def call_task_to_dict(call_task: CallTaskRef) -> dict[str, Any]:
    """Serialize a CallTaskRef back to CALL-E's wire shape (webhook `data`)."""
    return {
        "id": call_task.id,
        "object": "call_task",
        "status": call_task.status,
        "task": call_task.task,
        "recipients": [_recipient_to_dict(r) for r in call_task.recipients],
        "structured_result": call_task.structured_result,
        "summary": call_task.summary,
        "task_completed": call_task.task_completed,
        "completion_confidence": (
            {
                "score": call_task.completion_confidence.score,
                "label": call_task.completion_confidence.label,
            }
            if call_task.completion_confidence
            else None
        ),
        "evidence": [],
        "metadata": call_task.metadata,
        "failure_code": call_task.failure_code,
        "failure_message": call_task.failure_message,
        "created_at": call_task.created_at.isoformat(),
        "completed_at": call_task.completed_at.isoformat() if call_task.completed_at else None,
    }


class MockCallEAdapter:
    """Implements CallProviderPort by simulating CALL-E. Zero real network calls to CALL-E."""

    def __init__(
        self,
        *,
        http_client: httpx.AsyncClient,
        webhook_delay_seconds: float = 0.05,
        seed: int | None = None,
    ) -> None:
        self._http = http_client
        self._webhook_delay_seconds = webhook_delay_seconds
        self._rng = random.Random(seed)
        self._calls: dict[str, CallTaskRef] = {}
        self._pending_webhooks: dict[str, asyncio.Task[None]] = {}

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
    ) -> CallTaskRef:
        del result_schema, idempotency_key  # unused by the simulation
        now = datetime.now(UTC)
        call_id = f"call_{secrets.token_hex(12)}"

        recipient_refs = []
        any_completed = False
        for recipient in recipients:
            status, structured_result, failure_code = _simulate_recipient(self._rng)
            any_completed = any_completed or status == "completed"
            phone = recipient.phones[0]
            recipient_refs.append(
                CallRecipientResultRef(
                    id=f"recip_{secrets.token_hex(8)}",
                    phones=list(recipient.phones),
                    status=status,
                    structured_result=(
                        structured_result if recipient_result_schema is not None else None
                    ),
                    summary=_SYNTHETIC_NOTE if status == "completed" else None,
                    attempts=[
                        CallAttemptRef(
                            id=f"attempt_{secrets.token_hex(8)}",
                            phone=phone,
                            status=status,
                            started_at=now,
                            completed_at=now,
                            summary=None,
                            transcript_turns=[
                                TranscriptTurnRef(
                                    speaker="bot", text=_SYNTHETIC_NOTE, offset_seconds=0
                                )
                            ]
                            if status == "completed"
                            else [],
                            provider_call_id=None,
                            failure_code=failure_code,
                            failure_message=(
                                "Simulated: recipient did not answer." if failure_code else None
                            ),
                        )
                    ],
                )
            )

        call_task = CallTaskRef(
            id=call_id,
            status="completed" if any_completed else "failed",
            task=task,
            recipients=recipient_refs,
            structured_result=None,
            summary=_SYNTHETIC_NOTE,
            task_completed=any_completed,
            completion_confidence=(
                CompletionConfidenceRef(score=round(self._rng.uniform(0.6, 0.99), 2), label="high")
                if any_completed
                else None
            ),
            failure_code=None if any_completed else "no_recipients_reached",
            failure_message=None if any_completed else "Simulated: no recipient answered.",
            metadata=metadata or {},
            created_at=now,
            completed_at=now,
        )
        self._calls[call_id] = call_task

        webhook_task = asyncio.create_task(self._fire_webhook(call_task, webhook_url))
        self._pending_webhooks[call_id] = webhook_task
        return call_task

    async def get_call(self, call_id: str) -> CallTaskRef:
        call_task = self._calls.get(call_id)
        if call_task is None:
            raise NotFoundError(f"call {call_id} not found")
        return call_task

    async def list_call_events(self, call_id: str) -> list[CallEventRef]:
        call_task = await self.get_call(call_id)
        event_type = "call.completed" if call_task.task_completed else "call.failed"
        return [
            CallEventRef(
                id=f"evt_{secrets.token_hex(8)}",
                type=event_type,
                call_id=call_task.id,
                created_at=call_task.completed_at or call_task.created_at,
                level="info",
                status=call_task.status,
                message=_SYNTHETIC_NOTE,
                details={},
            )
        ]

    async def wait_for_webhook(self, call_id: str) -> None:
        """Test helper: await the deferred webhook fire for `call_id`."""
        webhook_task = self._pending_webhooks.get(call_id)
        if webhook_task is not None:
            await webhook_task

    async def _fire_webhook(self, call_task: CallTaskRef, webhook_url: str) -> None:
        await asyncio.sleep(self._webhook_delay_seconds)
        event_id = f"evt_{secrets.token_hex(12)}"
        event_type = "call.completed" if call_task.task_completed else "call.failed"
        payload = {
            "id": event_id,
            "type": event_type,
            "created_at": datetime.now(UTC).isoformat(),
            "data": call_task_to_dict(call_task),
        }
        await self._http.post(webhook_url, json=payload, headers={"CALL-E-Event-Id": event_id})
