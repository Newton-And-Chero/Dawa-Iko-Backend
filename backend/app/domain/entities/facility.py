"""Facility entity."""

from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID, uuid4

from app.domain.enums import FacilitySource, FacilityType, PhoneVerificationStatus


@dataclass
class Facility:
    name: str
    type: FacilityType
    county: str
    sub_county: str
    ward: str
    gps_lat: float
    gps_lng: float
    phone_number: str
    source: FacilitySource
    id: UUID = field(default_factory=uuid4)
    kmhfl_code: str | None = None
    operational_status: bool = True
    last_verified_at: datetime | None = None
    reliability_score: float | None = None
    phone_verification_status: PhoneVerificationStatus = PhoneVerificationStatus.UNVERIFIED
