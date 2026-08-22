"""Add Call provider correlation ids and the webhook_events idempotency ledger.

Revision ID: 0003
Revises: 0002
Create Date: 2026-08-20
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("calls", sa.Column("provider_call_id", sa.String(length=100), nullable=True))
    op.add_column(
        "calls", sa.Column("provider_recipient_id", sa.String(length=100), nullable=True)
    )
    op.create_index("ix_calls_provider_call_id", "calls", ["provider_call_id"], unique=False)

    op.create_table(
        "webhook_events",
        sa.Column("id", sa.String(length=100), nullable=False),
        sa.Column(
            "received_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("webhook_events")
    op.drop_index("ix_calls_provider_call_id", table_name="calls")
    op.drop_column("calls", "provider_recipient_id")
    op.drop_column("calls", "provider_call_id")
