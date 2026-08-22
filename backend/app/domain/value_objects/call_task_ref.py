"""Framework-free mirrors of CALL-E's call-task shapes.

These keep CALL-E's wire format (and the `calle-ai`/httpx types that parse it)
out of `application/` — everything above `infrastructure/call_e/` works with
these dataclasses only.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass(frozen=True)
class CallRecipient:
    """One outbound recipient we ask CALL-E to dial."""

    phones: list[str]
    region: str
    locale: str


@dataclass(frozen=True)
class CompletionConfidenceRef:
    score: float
    label: str


@dataclass(frozen=True)
class TranscriptTurnRef:
    speaker: str
    text: str
    offset_seconds: int | None = None


@dataclass(frozen=True)
class CallAttemptRef:
    id: str
    phone: str
    status: str
    started_at: datetime | None
    completed_at: datetime | None
    summary: str | None
    transcript_turns: list[TranscriptTurnRef]
    provider_call_id: str | None
    failure_code: str | None
    failure_message: str | None


@dataclass(frozen=True)
class CallRecipientResultRef:
    id: str
    phones: list[str]
    status: str
    structured_result: dict[str, Any] | None
    summary: str | None
    attempts: list[CallAttemptRef] = field(default_factory=list)


@dataclass(frozen=True)
class CallTaskRef:
    id: str
    status: str
    task: str
    recipients: list[CallRecipientResultRef]
    structured_result: dict[str, Any] | None
    summary: str | None
    task_completed: bool | None
    completion_confidence: CompletionConfidenceRef | None
    failure_code: str | None
    failure_message: str | None
    metadata: dict[str, Any]
    created_at: datetime
    completed_at: datetime | None


@dataclass(frozen=True)
class CallEventRef:
    id: str
    type: str
    call_id: str
    created_at: datetime
    level: str
    status: str
    message: str
    details: dict[str, Any]
