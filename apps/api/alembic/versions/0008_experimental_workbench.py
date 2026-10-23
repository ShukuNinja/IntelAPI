"""Persist workbench experiments and approach runs."""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0008_experimental_workbench"
down_revision: str | None = "0007_findings_evidence"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "experiments",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_by_user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("specification_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(160), nullable=False),
        sa.Column("configuration", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["specification_id"], ["api_specifications.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_experiments_project_created",
        "experiments",
        ["project_id", sa.text("created_at DESC")],
    )

    op.create_table(
        "experiment_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("experiment_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("campaign_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("approach", sa.String(32), nullable=False),
        sa.Column("configuration", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("generation_metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(
            "approach IN ('llm_baseline','semantic_assisted','feedback_guided','evidence_backed')",
            name="ck_experiment_runs_approach",
        ),
        sa.ForeignKeyConstraint(["experiment_id"], ["experiments.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["campaign_id"], ["campaigns.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("campaign_id", name="uq_experiment_runs_campaign"),
        sa.UniqueConstraint("experiment_id", "approach", name="uq_experiment_runs_approach"),
    )
    op.create_index(
        "ix_experiment_runs_experiment", "experiment_runs", ["experiment_id", "created_at"]
    )


def downgrade() -> None:
    op.drop_index("ix_experiment_runs_experiment", table_name="experiment_runs")
    op.drop_table("experiment_runs")
    op.drop_index("ix_experiments_project_created", table_name="experiments")
    op.drop_table("experiments")
