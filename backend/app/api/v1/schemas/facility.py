"""Facility request/response schemas — field names mirror the `Facility`
domain entity exactly (Sprint 01)."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel

from app.domain.enums import FacilitySource, FacilityType, PhoneVerificationStatus


class FacilityIn(BaseModel):
    name: str
    type: FacilityType
    county: str
    sub_county: str
    ward: str
    gps_lat: float
    gps_lng: float
    phone_number: str
    kmhfl_code: str | None = None


class FacilityEditIn(BaseModel):
    name: str | None = None
    type: FacilityType | None = None
    county: str | None = None
    sub_county: str | None = None
    ward: str | None = None
    gps_lat: float | None = None
    gps_lng: float | None = None
    phone_number: str | None = None
    kmhfl_code: str | None = None
    operational_status: bool | None = None


class VerifyPhoneIn(BaseModel):
    status: PhoneVerificationStatus


class FacilityOut(BaseModel):
    id: UUID
    name: str
    type: FacilityType
    county: str
    sub_county: str
    ward: str
    gps_lat: float
    gps_lng: float
    phone_number: str
    source: FacilitySource
    kmhfl_code: str | None
    operational_status: bool
    last_verified_at: datetime | None
    reliability_score: float | None
    phone_verification_status: PhoneVerificationStatus
