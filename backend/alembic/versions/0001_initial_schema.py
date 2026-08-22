"""Initial schema — all Sprint 01 entities.

Revision ID: 0001
Revises:
Create Date: 2026-08-20
"""

from collections.abc import Sequence

import geoalchemy2
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0001"
down_revision: str | None = None
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS postgis")

    op.create_table(
        "users",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column(
            "role",
            sa.Enum("admin", "analyst", "viewer", "public", name="user_role"),
            nullable=False,
        ),
        sa.Column("org", sa.String(length=255), nullable=True),
        sa.Column("phone_number", sa.String(length=32), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "commodities",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column(
            "category",
            sa.Enum("essential_medicine", "vaccine", "supply", name="commodity_category"),
            nullable=False,
        ),
        sa.Column("keml_code", sa.String(length=50), nullable=True),
        sa.Column("aliases", postgresql.ARRAY(sa.String()), nullable=False),
        sa.Column("is_priority_watchlist", sa.Boolean(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "facilities",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column(
            "type",
            sa.Enum("public", "dispensary", "private_chemist", "faith_based", name="facility_type"),
            nullable=False,
        ),
        sa.Column("county", sa.String(length=100), nullable=False),
        sa.Column("sub_county", sa.String(length=100), nullable=False),
        sa.Column("ward", sa.String(length=100), nullable=False),
        sa.Column(
            "location",
            geoalchemy2.Geometry(
                geometry_type="POINT",
                srid=4326,
                from_text="ST_GeomFromEWKT",
                spatial_index=False,
            ),
            nullable=False,
        ),
        sa.Column("phone_number", sa.String(length=32), nullable=False),
        sa.Column("kmhfl_code", sa.String(length=50), nullable=True),
        sa.Column(
            "source", sa.Enum("kmhfl", "manual", "crowd", name="facility_source"), nullable=False
        ),
        sa.Column("operational_status", sa.Boolean(), nullable=False),
        sa.Column("last_verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reliability_score", sa.Float(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_facilities_location", "facilities", ["location"], unique=False, postgresql_using="gist"
    )
    op.create_index("ix_facilities_county", "facilities", ["county"], unique=False)
    op.create_index("ix_facilities_sub_county", "facilities", ["sub_county"], unique=False)
    op.create_index("ix_facilities_ward", "facilities", ["ward"], unique=False)

    op.create_table(
        "sweeps",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("commodity_id", sa.Uuid(), nullable=False),
        sa.Column("geography_scope", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "trigger_type",
            sa.Enum("on_demand", "scheduled", name="sweep_trigger"),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.Enum("queued", "in_progress", "completed", name="sweep_status"),
            nullable=False,
        ),
        sa.Column("requester_id", sa.Uuid(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["commodity_id"], ["commodities.id"]),
        sa.ForeignKeyConstraint(["requester_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "calls",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("sweep_id", sa.Uuid(), nullable=False),
        sa.Column("facility_id", sa.Uuid(), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "queued",
                "in_progress",
                "completed",
                "failed",
                "canceled",
                "no_answer",
                "voicemail",
                name="call_status",
            ),
            nullable=False,
        ),
        sa.Column("attempt_number", sa.Integer(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("transcript_url", sa.String(length=500), nullable=True),
        sa.Column("recording_url", sa.String(length=500), nullable=True),
        sa.ForeignKeyConstraint(["sweep_id"], ["sweeps.id"]),
        sa.ForeignKeyConstraint(["facility_id"], ["facilities.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_calls_facility_id_started_at", "calls", ["facility_id", "started_at"], unique=False
    )

    op.create_table(
        "availability_results",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("call_id", sa.Uuid(), nullable=False),
        sa.Column("facility_id", sa.Uuid(), nullable=False),
        sa.Column("commodity_id", sa.Uuid(), nullable=False),
        sa.Column("in_stock", sa.Enum("yes", "no", "unknown", name="stock_status"), nullable=False),
        sa.Column("quantity_band", sa.String(length=50), nullable=True),
        sa.Column("price_kes", sa.Numeric(precision=10, scale=2), nullable=True),
        sa.Column("last_restock_date", sa.Date(), nullable=True),
        sa.Column("can_hold", sa.Boolean(), nullable=True),
        sa.Column("hold_duration_hours", sa.Integer(), nullable=True),
        sa.Column("hold_reference_code", sa.String(length=100), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["call_id"], ["calls.id"]),
        sa.ForeignKeyConstraint(["facility_id"], ["facilities.id"]),
        sa.ForeignKeyConstraint(["commodity_id"], ["commodities.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_availability_results_commodity_id_created_at",
        "availability_results",
        ["commodity_id", "created_at"],
        unique=False,
    )

    op.create_table(
        "stockout_alerts",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("commodity_id", sa.Uuid(), nullable=False),
        sa.Column("geography", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "severity",
            sa.Enum("low", "medium", "high", "critical", name="escalation_severity"),
            nullable=False,
        ),
        sa.Column("facilities_checked_count", sa.Integer(), nullable=False),
        sa.Column("facilities_with_stock_count", sa.Integer(), nullable=False),
        sa.Column("triggered_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "status",
            sa.Enum("open", "acknowledged", "resolved", name="escalation_status"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["commodity_id"], ["commodities.id"]),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "subscribers",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("org", sa.String(length=255), nullable=True),
        sa.Column("phone", sa.String(length=32), nullable=True),
        sa.Column("email", sa.String(length=255), nullable=True),
        sa.Column("watchlist_commodities", postgresql.ARRAY(sa.Uuid()), nullable=False),
        sa.Column("watchlist_geography", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "notification_channel",
            sa.Enum("sms", "email", "webhook", name="notification_channel"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("subscribers")
    op.drop_table("stockout_alerts")
    op.drop_index(
        "ix_availability_results_commodity_id_created_at", table_name="availability_results"
    )
    op.drop_table("availability_results")
    op.drop_index("ix_calls_facility_id_started_at", table_name="calls")
    op.drop_table("calls")
    op.drop_table("sweeps")
    op.drop_index("ix_facilities_ward", table_name="facilities")
    op.drop_index("ix_facilities_sub_county", table_name="facilities")
    op.drop_index("ix_facilities_county", table_name="facilities")
    op.drop_index("ix_facilities_location", table_name="facilities")
    op.drop_table("facilities")
    op.drop_table("commodities")
    op.drop_table("users")

    for enum_name in (
        "notification_channel",
        "escalation_status",
        "escalation_severity",
        "stock_status",
        "call_status",
        "sweep_status",
        "sweep_trigger",
        "facility_source",
        "facility_type",
        "commodity_category",
        "user_role",
    ):
        sa.Enum(name=enum_name).drop(op.get_bind(), checkfirst=True)
