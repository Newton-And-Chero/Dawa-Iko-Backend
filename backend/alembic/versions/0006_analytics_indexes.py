from collections.abc import Sequence

from alembic import op

revision: str = "0006"
down_revision: str | None = "0005"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.create_index("ix_calls_sweep_id", "calls", ["sweep_id"])
    op.create_index("ix_availability_results_call_id", "availability_results", ["call_id"])
    op.create_index("ix_availability_results_facility_id", "availability_results", ["facility_id"])


def downgrade() -> None:
    op.drop_index("ix_availability_results_facility_id", table_name="availability_results")
    op.drop_index("ix_availability_results_call_id", table_name="availability_results")
    op.drop_index("ix_calls_sweep_id", table_name="calls")
