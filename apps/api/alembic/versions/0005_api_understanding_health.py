"""Persist API specifications, extracted knowledge, and health checks."""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0005_api_understanding_health"
down_revision: str | None = "0004_execution_evidence"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "api_specifications",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_by_user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(160), nullable=False),
        sa.Column("source_kind", sa.String(16), nullable=False),
        sa.Column("source_url", sa.Text(), nullable=True),
        sa.Column("spec_document", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("content_sha256", sa.String(64), nullable=False),
        sa.Column("spec_version", sa.Integer(), server_default="1", nullable=False),
        sa.Column("openapi_version", sa.String(32), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint("source_kind IN ('file', 'url')", name="ck_api_specs_source_kind"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("project_id", "content_sha256", name="uq_api_specs_project_hash"),
    )
    op.create_index(
        "ix_api_specs_project_created",
        "api_specifications",
        ["project_id", sa.text("created_at DESC")],
    )

    op.create_table(
        "api_operations",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("specification_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("operation_key", sa.String(255), nullable=False),
        sa.Column("method", sa.String(12), nullable=False),
        sa.Column("path_template", sa.Text(), nullable=False),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("operation_document", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["specification_id"], ["api_specifications.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("specification_id", "operation_key", name="uq_api_operations_spec_key"),
    )
    op.create_index(
        "ix_api_operations_spec_path", "api_operations", ["specification_id", "path_template"]
    )

    op.create_table(
        "knowledge_facts",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("specification_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("operation_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("execution_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("fact_type", sa.String(80), nullable=False),
        sa.Column("subject", sa.String(255), nullable=False),
        sa.Column("fact_value", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("provenance", sa.String(16), nullable=False),
        sa.Column("confidence", sa.Numeric(4, 3), nullable=True),
        sa.Column("source_ref", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(
            "provenance IN ('DECLARED', 'EXTRACTED', 'OBSERVED', 'INFERRED')",
            name="ck_knowledge_facts_provenance",
        ),
        sa.CheckConstraint(
            "confidence IS NULL OR confidence BETWEEN 0 AND 1", name="ck_knowledge_facts_confidence"
        ),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["specification_id"], ["api_specifications.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(["operation_id"], ["api_operations.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["execution_id"], ["executions.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_knowledge_facts_project_operation_type",
        "knowledge_facts",
        ["project_id", "operation_id", "fact_type"],
    )

    op.create_table(
        "health_checks",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("saved_request_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("name", sa.String(160), nullable=False),
        sa.Column("definition", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("enabled", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["saved_request_id"], ["saved_requests.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_health_checks_project_enabled_updated",
        "health_checks",
        ["project_id", "enabled", sa.text("updated_at DESC")],
    )

    op.create_table(
        "assertion_results",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("execution_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("health_check_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("assertion_type", sa.String(32), nullable=False),
        sa.Column("passed", sa.Boolean(), nullable=False),
        sa.Column("expected", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("actual", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("message", sa.String(2000), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["execution_id"], ["executions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["health_check_id"], ["health_checks.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_assertion_results_execution", "assertion_results", ["execution_id"])
    op.create_index(
        "ix_assertion_results_health_created",
        "assertion_results",
        ["health_check_id", sa.text("created_at DESC")],
    )


def downgrade() -> None:
    op.drop_index("ix_assertion_results_health_created", table_name="assertion_results")
    op.drop_index("ix_assertion_results_execution", table_name="assertion_results")
    op.drop_table("assertion_results")
    op.drop_index("ix_health_checks_project_enabled_updated", table_name="health_checks")
    op.drop_table("health_checks")
    op.drop_index("ix_knowledge_facts_project_operation_type", table_name="knowledge_facts")
    op.drop_table("knowledge_facts")
    op.drop_index("ix_api_operations_spec_path", table_name="api_operations")
    op.drop_table("api_operations")
    op.drop_index("ix_api_specs_project_created", table_name="api_specifications")
    op.drop_table("api_specifications")
