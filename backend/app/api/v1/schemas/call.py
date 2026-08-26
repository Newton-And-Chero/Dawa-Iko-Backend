"""Call response schema — field names mirror the `Call` domain entity
exactly (Sprint 01). Includes transcript/recording URLs, so every route
returning this requires at least `viewer` (RULES.md's data-minimization
default for anything containing a transcript)."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel

from app.domain.enums import CallStatus


class CallOut(BaseModel):
    id: UUID
    sweep_id: UUID
    facility_id: UUID
    status: CallStatus
    attempt_number: int
    started_at: datetime | None
    ended_at: datetime | None
    transcript_url: str | None
    recording_url: str | None
