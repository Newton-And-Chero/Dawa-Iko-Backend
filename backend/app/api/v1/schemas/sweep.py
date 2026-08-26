"""Sweep request/response schemas.

`GeographyScopeIn` mirrors `app.domain.value_objects.geography_scope`'s
tagged union as a discriminated Pydantic union, using the exact same "kind"
keys `geography_scope_from_dict` already parses — so converting a validated
request body to the domain `GeographyScope` is just `model_dump()` +
`geography_scope_from_dict()`, no separate mapping to maintain.
"""

from datetime import datetime
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
    """Body for `POST /sweeps/query` and `POST /sweeps/scheduled` — commodity
    by id or name/alias (PROJECT.md 2.2/2.6), geography as one GeographyScope
    variant."""

    commodity: str
    geography: GeographyScopeIn


class SweepAccepted(BaseModel):
    sweep_id: UUID


class SweepSummaryOut(BaseModel):
    """`GET /sweeps` list rows — field names mirror the `Sweep` domain entity
    exactly (Sprint 01). No per-sweep call-progress counts here (that's the
    `GET /sweeps/{sweep_id}` detail view, `SweepOut` below) — computing them
    for every row of a bulk list isn't worth the per-row query."""

    id: UUID
    commodity_id: UUID
    geography_scope: dict[str, Any]
    trigger_type: SweepTrigger
    status: SweepStatus
    requester_id: UUID | None
    created_at: datetime


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
