"""Persist real candidate execution reports."""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0007_execution_reports"
down_revision: str | None = "0006_specification_source_url"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "execution_reports",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("specification_id", sa.Uuid(), nullable=False),
        sa.Column("execution_id", sa.Uuid(), nullable=False),
        sa.Column("candidate_id", sa.String(length=64), nullable=False),
        sa.Column("report", sa.JSON(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["specification_id"], ["api_specifications.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(["execution_id"], ["executions.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("execution_id", name="uq_execution_reports_execution_id"),
    )
    op.create_index("ix_execution_reports_project_id", "execution_reports", ["project_id"])
    op.create_index(
        "ix_execution_reports_specification_id", "execution_reports", ["specification_id"]
    )
    op.create_index("ix_execution_reports_candidate_id", "execution_reports", ["candidate_id"])


def downgrade() -> None:
    op.drop_index("ix_execution_reports_candidate_id", table_name="execution_reports")
    op.drop_index("ix_execution_reports_specification_id", table_name="execution_reports")
    op.drop_index("ix_execution_reports_project_id", table_name="execution_reports")
    op.drop_table("execution_reports")
