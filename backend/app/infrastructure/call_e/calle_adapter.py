from datetime import datetime
from typing import Any

import httpx

from app.core.exceptions import (
    CallNotFoundError,
    CallNotReadyError,
    CallProviderError,
    ForbiddenError,
    IdempotencyConflictError,
    InsufficientBalanceError,
    InternalCallProviderError,
    InvalidPhoneError,
    InvalidRecipientError,
    InvalidRequestError,
    NoRecipientsError,
    PolicyViolationError,
    ProviderUnavailableError,
    RateLimitExceededError,
    RecipientBlockedError,
    RecipientResultSchemaInvalidError,
    ResultSchemaInvalidError,
    UnauthorizedError,
    UnsupportedLanguageError,
    UnsupportedRegionError,
)
from app.domain.value_objects.call_task_ref import (
    CallAttemptRef,
    CallEventRef,
    CallRecipient,
    CallRecipientResultRef,
    CallTaskRef,
    CompletionConfidenceRef,
    TranscriptTurnRef,
)

_ERROR_CODE_MAP: dict[str, type[CallProviderError]] = {
    "invalid_request": InvalidRequestError,
    "unauthorized": UnauthorizedError,
    "forbidden": ForbiddenError,
    "unsupported_region": UnsupportedRegionError,
    "unsupported_language": UnsupportedLanguageError,
    "invalid_phone": InvalidPhoneError,
    "invalid_recipient": InvalidRecipientError,
    "no_recipients": NoRecipientsError,
    "recipient_blocked": RecipientBlockedError,
    "policy_violation": PolicyViolationError,
    "call_not_ready": CallNotReadyError,
    "result_schema_invalid": ResultSchemaInvalidError,
    "recipient_result_schema_invalid": RecipientResultSchemaInvalidError,
    "rate_limit_exceeded": RateLimitExceededError,
    "insufficient_balance": InsufficientBalanceError,
    "idempotency_conflict": IdempotencyConflictError,
    "provider_unavailable": ProviderUnavailableError,
    "internal_error": InternalCallProviderError,
    "not_found": CallNotFoundError,
}


def _parse_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _parse_confidence(data: dict[str, Any] | None) -> CompletionConfidenceRef | None:
    if data is None:
        return None
    return CompletionConfidenceRef(score=data["score"], label=data["label"])


def _parse_attempt(data: dict[str, Any]) -> CallAttemptRef:
    return CallAttemptRef(
        id=data["id"],
        phone=data["phone"],
        status=data["status"],
        started_at=_parse_datetime(data.get("started_at")),
        completed_at=_parse_datetime(data.get("completed_at")),
        summary=data.get("summary"),
        transcript_turns=[
            TranscriptTurnRef(
                offset_seconds=turn.get("offset_seconds"),
                speaker=turn["speaker"],
                text=turn["text"],
            )
            for turn in data.get("transcript_turns", [])
        ],
        provider_call_id=data.get("provider_call_id"),
        failure_code=data.get("failure_code"),
        failure_message=data.get("failure_message"),
    )


def _parse_recipient(data: dict[str, Any]) -> CallRecipientResultRef:
    return CallRecipientResultRef(
        id=data["id"],
        phones=list(data["phones"]),
        status=data["status"],
        structured_result=data.get("structured_result"),
        summary=data.get("summary"),
        locale=data.get("locale"),
        region=data.get("region"),
        attempts=[_parse_attempt(a) for a in data.get("attempts", [])],
    )


def _parse_call_task(data: dict[str, Any]) -> CallTaskRef:
    return CallTaskRef(
        id=data["id"],
        status=data["status"],
        task=data["task"],
        recipients=[_parse_recipient(r) for r in data.get("recipients", [])],
        structured_result=data.get("structured_result"),
        summary=data.get("summary"),
        task_completed=data.get("task_completed"),
        completion_confidence=_parse_confidence(data.get("completion_confidence")),
        evidence=[str(item) for item in data.get("evidence") or []],
        failure_code=data.get("failure_code"),
        failure_message=data.get("failure_message"),
        metadata=data.get("metadata") or {},
        created_at=_parse_datetime(data["created_at"]) or datetime.min,
        completed_at=_parse_datetime(data.get("completed_at")),
    )


def _raise_for_error(response: httpx.Response) -> None:
    if response.status_code < 400:
        return
    try:
        error = response.json()["error"]
        code, message = error["code"], error["message"]
    except (KeyError, ValueError):
        response.raise_for_status()
        return
    exc_cls = _ERROR_CODE_MAP.get(code, CallProviderError)
    raise exc_cls(code, message)


class CallEAdapter:
    def __init__(
        self, *, base_url: str, api_key: str, http_client: httpx.AsyncClient | None = None
    ) -> None:
        self._http = http_client or httpx.AsyncClient(
            base_url=base_url, headers={"Authorization": f"Bearer {api_key}"}, timeout=30.0
        )

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
        body: dict[str, Any] = {
            "task": task,
            "recipients": [
                {"phones": r.phones, "region": r.region, "locale": r.locale} for r in recipients
            ],
            "webhook_url": webhook_url,
        }
        if result_schema is not None:
            body["result_schema"] = result_schema
        if recipient_result_schema is not None:
            body["recipient_result_schema"] = recipient_result_schema
        if metadata is not None:
            body["metadata"] = metadata

        response = await self._http.post(
            "/v1/calls", json=body, headers={"Idempotency-Key": idempotency_key}
        )
        _raise_for_error(response)
        return _parse_call_task(response.json())

    async def get_call(self, call_id: str) -> CallTaskRef:
        response = await self._http.get(f"/v1/calls/{call_id}")
        _raise_for_error(response)
        return _parse_call_task(response.json())

    async def list_call_events(self, call_id: str) -> list[CallEventRef]:
        response = await self._http.get(f"/v1/calls/{call_id}/events")
        _raise_for_error(response)
        data = response.json()
        return [
            CallEventRef(
                id=e["id"],
                type=e["type"],
                call_id=e["call_id"],
                created_at=_parse_datetime(e["created_at"]) or datetime.min,
                level=e["level"],
                status=e["status"],
                message=e["message"],
                details=e.get("details") or {},
            )
            for e in data.get("data", [])
        ]
