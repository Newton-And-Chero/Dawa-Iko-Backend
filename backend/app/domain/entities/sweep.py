from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from app.domain.enums import SweepStatus, SweepTrigger


@dataclass
class Sweep:
    commodity_id: UUID
    geography_scope: dict[str, Any]
    trigger_type: SweepTrigger
    id: UUID = field(default_factory=uuid4)
    status: SweepStatus = SweepStatus.QUEUED
    requester_id: UUID | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
