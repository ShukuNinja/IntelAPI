"""Persist classified findings and evidence source references."""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0007_findings_evidence"
down_revision: str | None = "0006_testing_campaigns"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "findings",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("campaign_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("test_case_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("execution_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("finding_key", sa.String(255), nullable=False),
        sa.Column("title", sa.String(240), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("classification", sa.String(48), nullable=False),
        sa.Column("machine_severity", sa.String(16), nullable=False),
        sa.Column("confidence", sa.Numeric(4, 3), nullable=True),
        sa.Column("user_status", sa.String(24), server_default="open", nullable=False),
        sa.Column("user_severity", sa.String(16), nullable=True),
        sa.Column("triage_note", sa.Text(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(
            "classification IN ('assertion_mismatch','schema_mismatch')",
            name="ck_findings_classification",
        ),
        sa.CheckConstraint(
            "machine_severity IN ('info','low','medium','high','critical')",
            name="ck_findings_machine_severity",
        ),
        sa.CheckConstraint(
            "user_status IN ('open','confirmed','accepted','resolved','false_positive')",
            name="ck_findings_user_status",
        ),
        sa.CheckConstraint(
            "user_severity IS NULL OR user_severity IN ('low','medium','high','critical')",
            name="ck_findings_user_severity",
        ),
        sa.CheckConstraint(
            "confidence IS NULL OR confidence BETWEEN 0 AND 1", name="ck_findings_confidence"
        ),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["campaign_id"], ["campaigns.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["test_case_id"], ["test_cases.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["execution_id"], ["executions.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("project_id", "finding_key", name="uq_findings_project_key"),
    )
    op.create_index(
        "ix_findings_project_status_created",
        "findings",
        ["project_id", "user_status", sa.text("created_at DESC")],
    )
    op.create_table(
        "evidence_references",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("finding_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("execution_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("assertion_result_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("specification_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("operation_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("knowledge_fact_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("provenance", sa.String(16), nullable=False),
        sa.Column("evidence_type", sa.String(80), nullable=False),
        sa.Column("excerpt", sa.Text(), nullable=True),
        sa.Column(
            "metadata", postgresql.JSONB(astext_type=sa.Text()), server_default="{}", nullable=False
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(
            "provenance IN ('DECLARED','EXTRACTED','OBSERVED','INFERRED')",
            name="ck_evidence_references_provenance",
        ),
        sa.CheckConstraint(
            "execution_id IS NOT NULL OR assertion_result_id IS NOT NULL "
            "OR specification_id IS NOT NULL OR operation_id IS NOT NULL "
            "OR knowledge_fact_id IS NOT NULL",
            name="ck_evidence_references_source",
        ),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["finding_id"], ["findings.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["execution_id"], ["executions.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(
            ["assertion_result_id"], ["assertion_results.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["specification_id"], ["api_specifications.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(["operation_id"], ["api_operations.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["knowledge_fact_id"], ["knowledge_facts.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_evidence_references_project_finding",
        "evidence_references",
        ["project_id", "finding_id"],
    )
    op.create_index("ix_evidence_references_execution", "evidence_references", ["execution_id"])


def downgrade() -> None:
    op.drop_index("ix_evidence_references_execution", table_name="evidence_references")
    op.drop_index("ix_evidence_references_project_finding", table_name="evidence_references")
    op.drop_table("evidence_references")
    op.drop_index("ix_findings_project_status_created", table_name="findings")
    op.drop_table("findings")
