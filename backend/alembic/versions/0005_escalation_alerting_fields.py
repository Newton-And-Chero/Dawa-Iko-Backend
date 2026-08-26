"""Add StockoutAlert.acknowledgment_note and Subscriber.webhook_url, needed
for Sprint 07's acknowledge/resolve tracking and webhook notification channel.

Revision ID: 0005
Revises: 0004
Create Date: 2026-08-26
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0005"
down_revision: str | None = "0004"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("stockout_alerts", sa.Column("acknowledgment_note", sa.Text(), nullable=True))
    op.add_column("subscribers", sa.Column("webhook_url", sa.String(length=2048), nullable=True))


def downgrade() -> None:
    op.drop_column("subscribers", "webhook_url")
    op.drop_column("stockout_alerts", "acknowledgment_note")
