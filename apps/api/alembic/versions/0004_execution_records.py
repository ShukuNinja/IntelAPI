"""Store bounded execution metadata without credentials or response bodies."""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0004_execution_records"
down_revision: str | None = "0003_api_specifications"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "executions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("outcome", sa.String(length=32), nullable=False),
        sa.Column("request_snapshot", sa.JSON(), nullable=False),
        sa.Column("status_code", sa.Integer(), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("response_headers", sa.JSON(), nullable=True),
        sa.Column("response_excerpt", sa.Text(), nullable=True),
        sa.Column("response_size_bytes", sa.Integer(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_summary", sa.String(length=500), nullable=True),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_executions_project_id", "executions", ["project_id"])


def downgrade() -> None:
    op.drop_index("ix_executions_project_id", table_name="executions")
    op.drop_table("executions")
