"""StockoutAlert request/response schemas — field names mirror the
`StockoutAlert` domain entity exactly (Sprint 01), wired to a real router
with real data in Sprint 07."""

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel

from app.domain.enums import EscalationSeverity, EscalationStatus


class StockoutAlertOut(BaseModel):
    id: UUID
    commodity_id: UUID
    geography: dict[str, Any]
    severity: EscalationSeverity
    facilities_checked_count: int
    facilities_with_stock_count: int
    triggered_at: datetime
    status: EscalationStatus
    acknowledgment_note: str | None


class EscalationNoteIn(BaseModel):
    note: str | None = None
