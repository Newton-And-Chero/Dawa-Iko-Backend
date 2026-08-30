from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import UUID, uuid4

from app.domain.enums import StockStatus


@dataclass
class AvailabilityResult:
    call_id: UUID
    facility_id: UUID
    commodity_id: UUID
    in_stock: StockStatus
    id: UUID = field(default_factory=uuid4)
    quantity_band: str | None = None
    price_kes: Decimal | None = None
    last_restock_date: date | None = None
    can_hold: bool | None = None
    hold_duration_hours: int | None = None
    hold_reference_code: str | None = None
    confidence: float | None = None
    notes: str | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
