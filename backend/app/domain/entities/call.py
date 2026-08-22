"""Call entity."""

from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID, uuid4

from app.domain.enums import CallStatus


@dataclass
class Call:
    sweep_id: UUID
    facility_id: UUID
    id: UUID = field(default_factory=uuid4)
    status: CallStatus = CallStatus.QUEUED
    attempt_number: int = 1
    started_at: datetime | None = None
    ended_at: datetime | None = None
    transcript_url: str | None = None
    recording_url: str | None = None
    # CALL-E's own call task id (e.g. "call_...") and this facility's recipient
    # id within that task — set once place_call() returns, used by the webhook
    # handler to find the right Call row for an inbound event.
    provider_call_id: str | None = None
    provider_recipient_id: str | None = None
