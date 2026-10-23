"""Persist imported specifications and normalized operation catalogs."""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0003_api_specifications"
down_revision: str | None = "0002_identity_projects"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "api_specifications",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("spec_version", sa.String(length=32), nullable=False),
        sa.Column("source_format", sa.String(length=8), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("source_document", sa.JSON(), nullable=False),
        sa.Column("normalized_operations", sa.JSON(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("project_id", "content_hash", name="uq_spec_project_hash"),
    )
    op.create_index("ix_api_specifications_project_id", "api_specifications", ["project_id"])


def downgrade() -> None:
    op.drop_index("ix_api_specifications_project_id", table_name="api_specifications")
    op.drop_table("api_specifications")
