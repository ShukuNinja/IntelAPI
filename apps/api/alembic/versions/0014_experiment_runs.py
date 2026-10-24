"""Persist reproducible contract and semantic experiment runs."""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0014_experiment_runs"
down_revision: str | None = "0013_collections"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "experiment_runs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("specification_id", sa.Uuid(), nullable=False),
        sa.Column("approach", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("configuration", sa.JSON(), nullable=False),
        sa.Column("result", sa.JSON(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["specification_id"], ["api_specifications.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_experiment_runs_project_id", "experiment_runs", ["project_id"])
    op.create_index("ix_experiment_runs_specification_id", "experiment_runs", ["specification_id"])
    op.create_index("ix_experiment_runs_approach", "experiment_runs", ["approach"])


def downgrade() -> None:
    op.drop_index("ix_experiment_runs_approach", table_name="experiment_runs")
    op.drop_index("ix_experiment_runs_specification_id", table_name="experiment_runs")
    op.drop_index("ix_experiment_runs_project_id", table_name="experiment_runs")
    op.drop_table("experiment_runs")
