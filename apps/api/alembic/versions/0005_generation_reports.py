"""Persist deterministic candidate generation reports."""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0005_generation_reports"
down_revision: str | None = "0004_execution_records"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "generation_reports",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("specification_id", sa.Uuid(), nullable=False),
        sa.Column("policy_version", sa.String(length=64), nullable=False),
        sa.Column("report", sa.JSON(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["specification_id"], ["api_specifications.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_generation_reports_project_id", "generation_reports", ["project_id"])
    op.create_index(
        "ix_generation_reports_specification_id", "generation_reports", ["specification_id"]
    )


def downgrade() -> None:
    op.drop_index("ix_generation_reports_specification_id", table_name="generation_reports")
    op.drop_index("ix_generation_reports_project_id", table_name="generation_reports")
    op.drop_table("generation_reports")
