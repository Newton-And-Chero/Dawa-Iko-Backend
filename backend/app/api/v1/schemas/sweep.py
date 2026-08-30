from datetime import datetime
from decimal import Decimal
from typing import Annotated, Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field

from app.domain.enums import CallStatus, SweepStatus, SweepTrigger


class CountyScopeIn(BaseModel):
    kind: Literal["county"] = "county"
    county: str


class SubCountyScopeIn(BaseModel):
    kind: Literal["sub_county"] = "sub_county"
    sub_county: str


class WardScopeIn(BaseModel):
    kind: Literal["ward"] = "ward"
    ward: str


class RadiusScopeIn(BaseModel):
    kind: Literal["radius"] = "radius"
    lat: float
    lng: float
    radius_km: float


class NearestNScopeIn(BaseModel):
    kind: Literal["nearest_n"] = "nearest_n"
    lat: float
    lng: float
    n: int


GeographyScopeIn = Annotated[
    CountyScopeIn | SubCountyScopeIn | WardScopeIn | RadiusScopeIn | NearestNScopeIn,
    Field(discriminator="kind"),
]


class SweepQueryIn(BaseModel):
    commodity: str
    geography: GeographyScopeIn


class SweepAccepted(BaseModel):
    sweep_id: UUID


class SweepSummaryOut(BaseModel):
    id: UUID
    commodity_id: UUID
    geography_scope: dict[str, Any]
    trigger_type: SweepTrigger
    status: SweepStatus
    requester_id: UUID | None
    created_at: datetime


class PatientMatchOut(BaseModel):
    facility_id: UUID
    facility_name: str
    distance_meters: float | None
    price_kes: Decimal | None
    can_hold: bool | None
    hold_reference_code: str | None
    confidence: float | None


class SweepOut(BaseModel):
    sweep_id: UUID
    status: SweepStatus
    total_calls: int
    commodity_id: UUID
    geography_scope: dict[str, Any]
    trigger_type: SweepTrigger
    created_at: datetime
    requester_id: UUID | None
    counts_by_status: dict[CallStatus, int]
    matches: list[PatientMatchOut]
