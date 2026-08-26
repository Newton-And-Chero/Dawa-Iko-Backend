"""Add password_hash to users and a uniqueness constraint on phone_number,
needed for Sprint 05's /auth/login (users authenticate by phone_number since
the User entity has no email field).

Revision ID: 0004
Revises: 0003
Create Date: 2026-08-23
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("users", sa.Column("password_hash", sa.String(length=255), nullable=True))
    op.create_unique_constraint("uq_users_phone_number", "users", ["phone_number"])


def downgrade() -> None:
    op.drop_constraint("uq_users_phone_number", "users", type_="unique")
    op.drop_column("users", "password_hash")
