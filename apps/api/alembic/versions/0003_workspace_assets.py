"""Add workspace collections, environments, variables, and saved requests.

Revision ID: 0003_workspace_assets
Revises: ba3a950852cf
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0003_workspace_assets"
down_revision: str | None = "ba3a950852cf"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "collections",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column(
            "project_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["projects.id"],
            name="fk_collections_project_id_projects",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_collections"),
        sa.UniqueConstraint(
            "project_id",
            "name",
            name="uq_collections_project_name",
        ),
    )
    op.create_index(
        "ix_collections_project_updated",
        "collections",
        ["project_id", sa.text("updated_at DESC")],
        unique=False,
    )

    op.create_table(
        "environments",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column(
            "project_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("base_url", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["projects.id"],
            name="fk_environments_project_id_projects",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_environments"),
        sa.UniqueConstraint(
            "project_id",
            "name",
            name="uq_environments_project_name",
        ),
    )

    op.create_table(
        "environment_variables",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column(
            "environment_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column("key", sa.String(length=160), nullable=False),
        sa.Column("value_ciphertext", sa.LargeBinary(), nullable=True),
        sa.Column("value_plain", sa.Text(), nullable=True),
        sa.Column(
            "is_secret",
            sa.Boolean(),
            server_default=sa.false(),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            """
            (
                value_ciphertext IS NOT NULL
                AND value_plain IS NULL
            )
            OR
            (
                value_ciphertext IS NULL
                AND value_plain IS NOT NULL
            )
            """,
            name="ck_environment_variables_exactly_one_value",
        ),
        sa.CheckConstraint(
            "NOT is_secret OR value_ciphertext IS NOT NULL",
            name="ck_environment_variables_secret_encrypted",
        ),
        sa.ForeignKeyConstraint(
            ["environment_id"],
            ["environments.id"],
            name="fk_environment_variables_environment_id_environments",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_environment_variables"),
        sa.UniqueConstraint(
            "environment_id",
            "key",
            name="uq_environment_variables_environment_key",
        ),
    )
    op.create_index(
        "ix_environment_variables_environment",
        "environment_variables",
        ["environment_id"],
        unique=False,
    )

    op.create_table(
        "saved_requests",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column(
            "project_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column(
            "collection_id",
            postgresql.UUID(as_uuid=True),
            nullable=True,
        ),
        sa.Column(
            "environment_id",
            postgresql.UUID(as_uuid=True),
            nullable=True,
        ),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("method", sa.String(length=12), nullable=False),
        sa.Column("url_template", sa.Text(), nullable=False),
        sa.Column(
            "headers",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "query_params",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "body",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
        sa.Column(
            "body_type",
            sa.String(length=32),
            server_default=sa.text("'none'"),
            nullable=False,
        ),
        sa.Column(
            "auth_config",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "body_type IN "
            "('none', 'json', 'text', 'form_urlencoded', 'multipart')",
            name="ck_saved_requests_body_type",
        ),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["projects.id"],
            name="fk_saved_requests_project_id_projects",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["collection_id"],
            ["collections.id"],
            name="fk_saved_requests_collection_id_collections",
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["environment_id"],
            ["environments.id"],
            name="fk_saved_requests_environment_id_environments",
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_saved_requests"),
    )
    op.create_index(
        "ix_saved_requests_project_updated",
        "saved_requests",
        ["project_id", sa.text("updated_at DESC")],
        unique=False,
    )
    op.create_index(
        "ix_saved_requests_collection",
        "saved_requests",
        ["collection_id"],
        unique=False,
    )
    op.create_index(
        "ix_saved_requests_environment",
        "saved_requests",
        ["environment_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_saved_requests_environment",
        table_name="saved_requests",
    )
    op.drop_index(
        "ix_saved_requests_collection",
        table_name="saved_requests",
    )
    op.drop_index(
        "ix_saved_requests_project_updated",
        table_name="saved_requests",
    )
    op.drop_table("saved_requests")

    op.drop_index(
        "ix_environment_variables_environment",
        table_name="environment_variables",
    )
    op.drop_table("environment_variables")

    op.drop_table("environments")

    op.drop_index(
        "ix_collections_project_updated",
        table_name="collections",
    )
    op.drop_table("collections")