from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None

_ENUM = sa.Enum("unverified", "verified", "bounced", name="phone_verification_status")


def upgrade() -> None:
    _ENUM.create(op.get_bind(), checkfirst=True)
    op.add_column(
        "facilities",
        sa.Column(
            "phone_verification_status",
            _ENUM,
            nullable=False,
            server_default="unverified",
        ),
    )


def downgrade() -> None:
    op.drop_column("facilities", "phone_verification_status")
    _ENUM.drop(op.get_bind(), checkfirst=True)
