"""Persist saved requests and project environments."""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0008_request_resources"
down_revision: str | None = "0007_execution_reports"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "saved_requests",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("collection_name", sa.String(length=120), nullable=True),
        sa.Column("method", sa.String(length=10), nullable=False),
        sa.Column("url", sa.String(length=4096), nullable=False),
        sa.Column("headers", sa.JSON(), nullable=False),
        sa.Column("body", sa.Text(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_saved_requests_project_id", "saved_requests", ["project_id"])
    op.create_index("ix_saved_requests_collection_name", "saved_requests", ["collection_name"])
    op.create_table(
        "environments",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("base_url", sa.String(length=2048), nullable=True),
        sa.Column("variables", sa.JSON(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_environments_project_id", "environments", ["project_id"])


def downgrade() -> None:
    op.drop_index("ix_environments_project_id", table_name="environments")
    op.drop_table("environments")
    op.drop_index("ix_saved_requests_collection_name", table_name="saved_requests")
    op.drop_index("ix_saved_requests_project_id", table_name="saved_requests")
    op.drop_table("saved_requests")
