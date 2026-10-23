"""Persist human triage for safe execution observations."""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0009_finding_triage"
down_revision: str | None = "0008_request_resources"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "finding_triage",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("execution_report_id", sa.Uuid(), nullable=False),
        sa.Column("evidence_key", sa.String(length=96), nullable=False),
        sa.Column("classification", sa.String(length=32), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["execution_report_id"], ["execution_reports.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "execution_report_id", "evidence_key", name="uq_finding_triage_evidence"
        ),
    )
    op.create_index("ix_finding_triage_project_id", "finding_triage", ["project_id"])
    op.create_index(
        "ix_finding_triage_execution_report_id", "finding_triage", ["execution_report_id"]
    )


def downgrade() -> None:
    op.drop_index("ix_finding_triage_execution_report_id", table_name="finding_triage")
    op.drop_index("ix_finding_triage_project_id", table_name="finding_triage")
    op.drop_table("finding_triage")
