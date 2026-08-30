from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel

from app.domain.enums import StockStatus


class AvailabilityResultOut(BaseModel):
    id: UUID
    call_id: UUID
    facility_id: UUID
    commodity_id: UUID
    in_stock: StockStatus
    quantity_band: str | None
    price_kes: Decimal | None
    last_restock_date: date | None
    can_hold: bool | None
    hold_duration_hours: int | None
    hold_reference_code: str | None
    confidence: float | None
    notes: str | None
    created_at: datetime
