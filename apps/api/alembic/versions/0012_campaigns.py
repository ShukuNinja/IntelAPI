"""Add durable campaign jobs, test cases, and event history."""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0012_campaigns"
down_revision: str | None = "0011_environment_secrets"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "campaigns",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("created_by_user_id", sa.Uuid(), nullable=False),
        sa.Column("specification_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("state", sa.String(length=16), nullable=False),
        sa.Column("configuration", sa.JSON(), nullable=False),
        sa.Column("budget_max_executions", sa.Integer(), nullable=False),
        sa.Column("budget_max_iterations", sa.Integer(), nullable=False),
        sa.Column("budget_max_duration_seconds", sa.Integer(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancel_requested_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("failure_code", sa.String(length=64), nullable=True),
        sa.Column("failure_summary", sa.Text(), nullable=True),
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
    op.create_index("ix_campaigns_project_id", "campaigns", ["project_id"])
    op.create_index("ix_campaigns_state", "campaigns", ["state"])
    op.create_table(
        "campaign_jobs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("campaign_id", sa.Uuid(), nullable=False),
        sa.Column("state", sa.String(length=16), nullable=False),
        sa.Column(
            "available_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("lease_owner", sa.String(length=160), nullable=True),
        sa.Column("lease_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("attempt_count", sa.Integer(), nullable=False),
        sa.Column("last_error_code", sa.String(length=64), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["campaign_id"], ["campaigns.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("campaign_id"),
    )
    op.create_index("ix_campaign_jobs_state", "campaign_jobs", ["state"])
    op.create_table(
        "test_cases",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("campaign_id", sa.Uuid(), nullable=False),
        sa.Column("operation_id", sa.String(length=64), nullable=True),
        sa.Column("candidate_key", sa.String(length=255), nullable=False),
        sa.Column("category", sa.String(length=32), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("request_override", sa.JSON(), nullable=False),
        sa.Column("expected_behavior", sa.JSON(), nullable=True),
        sa.Column("generation_provenance", sa.String(length=16), nullable=False),
        sa.Column("state", sa.String(length=24), nullable=False),
        sa.Column("execution_id", sa.Uuid(), nullable=True),
        sa.Column("result", sa.JSON(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["campaign_id"], ["campaigns.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["execution_id"], ["executions.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("campaign_id", "candidate_key", name="uq_test_case_campaign_candidate"),
    )
    op.create_index("ix_test_cases_project_id", "test_cases", ["project_id"])
    op.create_index("ix_test_cases_campaign_id", "test_cases", ["campaign_id"])
    op.create_table(
        "campaign_events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("campaign_id", sa.Uuid(), nullable=False),
        sa.Column("sequence_number", sa.BigInteger(), nullable=False),
        sa.Column("event_type", sa.String(length=80), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["campaign_id"], ["campaigns.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("campaign_id", "sequence_number", name="uq_campaign_event_sequence"),
    )
    op.create_index("ix_campaign_events_campaign_id", "campaign_events", ["campaign_id"])
    with op.batch_alter_table("executions") as batch_op:
        batch_op.add_column(sa.Column("campaign_id", sa.Uuid(), nullable=True))
        batch_op.add_column(sa.Column("test_case_id", sa.Uuid(), nullable=True))
        batch_op.create_index("ix_executions_campaign_id", ["campaign_id"])
        batch_op.create_index("ix_executions_test_case_id", ["test_case_id"])
        batch_op.create_foreign_key(
            "fk_executions_campaign_id_campaigns",
            "campaigns",
            ["campaign_id"],
            ["id"],
            ondelete="SET NULL",
        )
        batch_op.create_foreign_key(
            "fk_executions_test_case_id_test_cases",
            "test_cases",
            ["test_case_id"],
            ["id"],
            ondelete="SET NULL",
        )


def downgrade() -> None:
    with op.batch_alter_table("executions") as batch_op:
        batch_op.drop_constraint("fk_executions_test_case_id_test_cases", type_="foreignkey")
        batch_op.drop_constraint("fk_executions_campaign_id_campaigns", type_="foreignkey")
        batch_op.drop_index("ix_executions_test_case_id")
        batch_op.drop_index("ix_executions_campaign_id")
        batch_op.drop_column("test_case_id")
        batch_op.drop_column("campaign_id")
    op.drop_index("ix_campaign_events_campaign_id", table_name="campaign_events")
    op.drop_table("campaign_events")
    op.drop_index("ix_test_cases_campaign_id", table_name="test_cases")
    op.drop_index("ix_test_cases_project_id", table_name="test_cases")
    op.drop_table("test_cases")
    op.drop_index("ix_campaign_jobs_state", table_name="campaign_jobs")
    op.drop_table("campaign_jobs")
    op.drop_index("ix_campaigns_state", table_name="campaigns")
    op.drop_index("ix_campaigns_project_id", table_name="campaigns")
    op.drop_table("campaigns")
