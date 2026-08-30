from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from app.domain.enums import EscalationSeverity, EscalationStatus


@dataclass
class StockoutAlert:
    commodity_id: UUID
    geography: dict[str, Any]
    severity: EscalationSeverity
    facilities_checked_count: int
    facilities_with_stock_count: int
    id: UUID = field(default_factory=uuid4)
    status: EscalationStatus = EscalationStatus.OPEN
    triggered_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    acknowledgment_note: str | None = None
