"""SQLAlchemy declarative models — one class per domain entity."""

from datetime import date, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from geoalchemy2 import Geometry
from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    Uuid,
    func,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from app.domain.enums import (
    CallStatus,
    CommodityCategory,
    EscalationSeverity,
    EscalationStatus,
    FacilitySource,
    FacilityType,
    NotificationChannel,
    PhoneVerificationStatus,
    StockStatus,
    SweepStatus,
    SweepTrigger,
    UserRole,
)


class Base(DeclarativeBase):
    pass


def _pg_enum(enum_cls: type, name: str) -> Enum:
    """A native Postgres enum type storing member *values* (e.g. "no_answer"), not names."""
    return Enum(enum_cls, name=name, values_callable=lambda obj: [e.value for e in obj])


class FacilityModel(Base):
    __tablename__ = "facilities"

    id: Mapped[UUID] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    type: Mapped[FacilityType] = mapped_column(
        _pg_enum(FacilityType, "facility_type"), nullable=False
    )
    county: Mapped[str] = mapped_column(String(100), nullable=False)
    sub_county: Mapped[str] = mapped_column(String(100), nullable=False)
    ward: Mapped[str] = mapped_column(String(100), nullable=False)
    location: Mapped[Any] = mapped_column(
        Geometry("POINT", srid=4326, spatial_index=False), nullable=False
    )
    phone_number: Mapped[str] = mapped_column(String(32), nullable=False)
    kmhfl_code: Mapped[str | None] = mapped_column(String(50), nullable=True)
    source: Mapped[FacilitySource] = mapped_column(
        _pg_enum(FacilitySource, "facility_source"), nullable=False
    )
    operational_status: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    last_verified_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    reliability_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    phone_verification_status: Mapped[PhoneVerificationStatus] = mapped_column(
        _pg_enum(PhoneVerificationStatus, "phone_verification_status"),
        nullable=False,
        default=PhoneVerificationStatus.UNVERIFIED,
        server_default=PhoneVerificationStatus.UNVERIFIED.value,
    )

    __table_args__ = (
        Index("ix_facilities_location", "location", postgresql_using="gist"),
        Index("ix_facilities_county", "county"),
        Index("ix_facilities_sub_county", "sub_county"),
        Index("ix_facilities_ward", "ward"),
    )


class CommodityModel(Base):
    __tablename__ = "commodities"

    id: Mapped[UUID] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    category: Mapped[CommodityCategory] = mapped_column(
        _pg_enum(CommodityCategory, "commodity_category"), nullable=False
    )
    keml_code: Mapped[str | None] = mapped_column(String(50), nullable=True)
    aliases: Mapped[list[str]] = mapped_column(ARRAY(String), nullable=False, default=list)
    is_priority_watchlist: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class SweepModel(Base):
    __tablename__ = "sweeps"

    id: Mapped[UUID] = mapped_column(primary_key=True)
    commodity_id: Mapped[UUID] = mapped_column(ForeignKey("commodities.id"), nullable=False)
    geography_scope: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    trigger_type: Mapped[SweepTrigger] = mapped_column(
        _pg_enum(SweepTrigger, "sweep_trigger"), nullable=False
    )
    status: Mapped[SweepStatus] = mapped_column(
        _pg_enum(SweepStatus, "sweep_status"), nullable=False
    )
    requester_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class CallModel(Base):
    __tablename__ = "calls"

    id: Mapped[UUID] = mapped_column(primary_key=True)
    sweep_id: Mapped[UUID] = mapped_column(ForeignKey("sweeps.id"), nullable=False)
    facility_id: Mapped[UUID] = mapped_column(ForeignKey("facilities.id"), nullable=False)
    status: Mapped[CallStatus] = mapped_column(_pg_enum(CallStatus, "call_status"), nullable=False)
    attempt_number: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    transcript_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    recording_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    provider_call_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    provider_recipient_id: Mapped[str | None] = mapped_column(String(100), nullable=True)

    __table_args__ = (
        Index("ix_calls_facility_id_started_at", "facility_id", "started_at"),
        Index("ix_calls_provider_call_id", "provider_call_id"),
    )


class AvailabilityResultModel(Base):
    __tablename__ = "availability_results"

    id: Mapped[UUID] = mapped_column(primary_key=True)
    call_id: Mapped[UUID] = mapped_column(ForeignKey("calls.id"), nullable=False)
    facility_id: Mapped[UUID] = mapped_column(ForeignKey("facilities.id"), nullable=False)
    commodity_id: Mapped[UUID] = mapped_column(ForeignKey("commodities.id"), nullable=False)
    in_stock: Mapped[StockStatus] = mapped_column(
        _pg_enum(StockStatus, "stock_status"), nullable=False
    )
    quantity_band: Mapped[str | None] = mapped_column(String(50), nullable=True)
    price_kes: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)
    last_restock_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    can_hold: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    hold_duration_hours: Mapped[int | None] = mapped_column(Integer, nullable=True)
    hold_reference_code: Mapped[str | None] = mapped_column(String(100), nullable=True)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        Index("ix_availability_results_commodity_id_created_at", "commodity_id", "created_at"),
    )


class StockoutAlertModel(Base):
    __tablename__ = "stockout_alerts"

    id: Mapped[UUID] = mapped_column(primary_key=True)
    commodity_id: Mapped[UUID] = mapped_column(ForeignKey("commodities.id"), nullable=False)
    geography: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    severity: Mapped[EscalationSeverity] = mapped_column(
        _pg_enum(EscalationSeverity, "escalation_severity"), nullable=False
    )
    facilities_checked_count: Mapped[int] = mapped_column(Integer, nullable=False)
    facilities_with_stock_count: Mapped[int] = mapped_column(Integer, nullable=False)
    triggered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    status: Mapped[EscalationStatus] = mapped_column(
        _pg_enum(EscalationStatus, "escalation_status"), nullable=False
    )


class SubscriberModel(Base):
    __tablename__ = "subscribers"

    id: Mapped[UUID] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    org: Mapped[str | None] = mapped_column(String(255), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(32), nullable=True)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    watchlist_commodities: Mapped[list[UUID]] = mapped_column(
        ARRAY(Uuid()), nullable=False, default=list
    )
    watchlist_geography: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    notification_channel: Mapped[NotificationChannel] = mapped_column(
        _pg_enum(NotificationChannel, "notification_channel"), nullable=False
    )


class WebhookEventModel(Base):
    """Idempotency ledger for inbound CALL-E webhook events (see workflows/03)."""

    __tablename__ = "webhook_events"

    id: Mapped[str] = mapped_column(String(100), primary_key=True)
    received_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class UserModel(Base):
    __tablename__ = "users"

    id: Mapped[UUID] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[UserRole] = mapped_column(_pg_enum(UserRole, "user_role"), nullable=False)
    org: Mapped[str | None] = mapped_column(String(255), nullable=True)
    phone_number: Mapped[str | None] = mapped_column(String(32), nullable=True, unique=True)
    password_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)
