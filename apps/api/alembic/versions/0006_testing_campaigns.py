"""Persist bounded test campaigns, cases, jobs, and append-only events."""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0006_testing_campaigns"
down_revision: str | None = "0005_api_understanding_health"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "campaigns",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_by_user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(160), nullable=False),
        sa.Column("state", sa.String(16), nullable=False),
        sa.Column("configuration", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("budget_max_executions", sa.Integer(), nullable=False),
        sa.Column("budget_max_iterations", sa.Integer(), nullable=False),
        sa.Column("budget_max_duration_seconds", sa.Integer(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancel_requested_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("failure_code", sa.String(64), nullable=True),
        sa.Column("failure_summary", sa.Text(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(
            "state IN ('queued','running','completed','failed','cancelled')",
            name="ck_campaigns_state",
        ),
        sa.CheckConstraint(
            "budget_max_executions BETWEEN 1 AND 1000", name="ck_campaigns_budget_executions"
        ),
        sa.CheckConstraint(
            "budget_max_iterations BETWEEN 1 AND 1000", name="ck_campaigns_budget_iterations"
        ),
        sa.CheckConstraint(
            "budget_max_duration_seconds BETWEEN 1 AND 86400", name="ck_campaigns_budget_duration"
        ),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_campaigns_project_created", "campaigns", ["project_id", sa.text("created_at DESC")]
    )
    op.create_index("ix_campaigns_state_created", "campaigns", ["state", "created_at"])
    op.create_table(
        "test_cases",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("campaign_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("operation_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("candidate_key", sa.String(255), nullable=False),
        sa.Column("category", sa.String(32), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("request_override", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("expected_behavior", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("generation_provenance", sa.String(16), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["campaign_id"], ["campaigns.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["operation_id"], ["api_operations.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "campaign_id", "candidate_key", name="uq_test_cases_campaign_candidate"
        ),
    )
    op.create_index("ix_test_cases_campaign_created", "test_cases", ["campaign_id", "created_at"])
    op.create_table(
        "campaign_jobs",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("campaign_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("state", sa.String(16), nullable=False),
        sa.Column(
            "available_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("lease_owner", sa.String(160), nullable=True),
        sa.Column("lease_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("attempt_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("last_error_code", sa.String(64), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(
            "state IN ('queued','leased','completed','failed','cancelled')",
            name="ck_campaign_jobs_state",
        ),
        sa.ForeignKeyConstraint(["campaign_id"], ["campaigns.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("campaign_id"),
    )
    op.create_index("ix_campaign_jobs_state_available", "campaign_jobs", ["state", "available_at"])
    op.create_index("ix_campaign_jobs_lease", "campaign_jobs", ["lease_expires_at"])
    op.create_table(
        "campaign_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("campaign_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("sequence_number", sa.BigInteger(), nullable=False),
        sa.Column("event_type", sa.String(80), nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["campaign_id"], ["campaigns.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("campaign_id", "sequence_number", name="uq_campaign_events_sequence"),
    )
    op.create_index(
        "ix_campaign_events_campaign_created", "campaign_events", ["campaign_id", "created_at"]
    )
    op.add_column(
        "executions", sa.Column("campaign_id", postgresql.UUID(as_uuid=True), nullable=True)
    )
    op.add_column(
        "executions", sa.Column("test_case_id", postgresql.UUID(as_uuid=True), nullable=True)
    )
    op.create_foreign_key(
        "fk_executions_campaign",
        "executions",
        "campaigns",
        ["campaign_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        "fk_executions_test_case",
        "executions",
        "test_cases",
        ["test_case_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index("ix_executions_campaign_created", "executions", ["campaign_id", "created_at"])
    op.create_index("ix_executions_test_case", "executions", ["test_case_id"])


def downgrade() -> None:
    op.drop_index("ix_executions_test_case", table_name="executions")
    op.drop_index("ix_executions_campaign_created", table_name="executions")
    op.drop_constraint("fk_executions_test_case", "executions", type_="foreignkey")
    op.drop_constraint("fk_executions_campaign", "executions", type_="foreignkey")
    op.drop_column("executions", "test_case_id")
    op.drop_column("executions", "campaign_id")
    op.drop_index("ix_campaign_events_campaign_created", table_name="campaign_events")
    op.drop_table("campaign_events")
    op.drop_index("ix_campaign_jobs_lease", table_name="campaign_jobs")
    op.drop_index("ix_campaign_jobs_state_available", table_name="campaign_jobs")
    op.drop_table("campaign_jobs")
    op.drop_index("ix_test_cases_campaign_created", table_name="test_cases")
    op.drop_table("test_cases")
    op.drop_index("ix_campaigns_state_created", table_name="campaigns")
    op.drop_index("ix_campaigns_project_created", table_name="campaigns")
    op.drop_table("campaigns")
