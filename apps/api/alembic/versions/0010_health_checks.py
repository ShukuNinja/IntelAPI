"""Persist health checks and their assertion results."""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0010_health_checks"
down_revision: str | None = "0009_finding_triage"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "health_checks",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("saved_request_id", sa.Uuid(), nullable=True),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("definition", sa.JSON(), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["saved_request_id"], ["saved_requests.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_health_checks_project_id", "health_checks", ["project_id"])
    op.create_index("ix_health_checks_saved_request_id", "health_checks", ["saved_request_id"])
    op.create_table(
        "assertion_results",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("execution_id", sa.Uuid(), nullable=False),
        sa.Column("assertion_type", sa.String(length=32), nullable=False),
        sa.Column("passed", sa.Boolean(), nullable=False),
        sa.Column("expected", sa.JSON(), nullable=True),
        sa.Column("actual", sa.JSON(), nullable=True),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["execution_id"], ["executions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_assertion_results_execution_id", "assertion_results", ["execution_id"])


def downgrade() -> None:
    op.drop_index("ix_assertion_results_execution_id", table_name="assertion_results")
    op.drop_table("assertion_results")
    op.drop_index("ix_health_checks_saved_request_id", table_name="health_checks")
    op.drop_index("ix_health_checks_project_id", table_name="health_checks")
    op.drop_table("health_checks")
