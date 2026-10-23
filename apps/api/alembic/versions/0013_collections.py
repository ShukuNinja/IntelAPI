"""Promote request collection labels to project-owned resources."""

from collections.abc import Sequence
from uuid import uuid4

import sqlalchemy as sa

from alembic import op

revision: str = "0013_collections"
down_revision: str | None = "0012_campaigns"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "collections",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("project_id", "name", name="uq_collection_project_name"),
    )
    op.create_index("ix_collections_project_id", "collections", ["project_id"])

    with op.batch_alter_table("saved_requests") as batch_op:
        batch_op.add_column(sa.Column("collection_id", sa.Uuid(), nullable=True))
        batch_op.create_foreign_key(
            "fk_saved_requests_collection_id_collections",
            "collections",
            ["collection_id"],
            ["id"],
            ondelete="SET NULL",
        )

    bind = op.get_bind()
    saved_requests = sa.table(
        "saved_requests",
        sa.column("id", sa.Uuid()),
        sa.column("project_id", sa.Uuid()),
        sa.column("collection_name", sa.String()),
    )
    collections = sa.table(
        "collections",
        sa.column("id", sa.Uuid()),
        sa.column("project_id", sa.Uuid()),
        sa.column("name", sa.String()),
    )
    legacy_groups = bind.execute(
        sa.select(saved_requests.c.project_id, saved_requests.c.collection_name)
        .where(saved_requests.c.collection_name.is_not(None))
        .where(saved_requests.c.collection_name != "")
        .distinct()
    )
    for project_id, collection_name in legacy_groups:
        collection_id = uuid4()
        bind.execute(
            collections.insert().values(
                id=collection_id, project_id=project_id, name=collection_name
            )
        )
        bind.execute(
            saved_requests.update()
            .where(saved_requests.c.project_id == project_id)
            .where(saved_requests.c.collection_name == collection_name)
            .values(collection_id=collection_id)
        )

    op.create_index("ix_saved_requests_collection_id", "saved_requests", ["collection_id"])
    op.drop_index("ix_saved_requests_collection_name", table_name="saved_requests")
    with op.batch_alter_table("saved_requests") as batch_op:
        batch_op.drop_column("collection_name")


def downgrade() -> None:
    op.add_column(
        "saved_requests", sa.Column("collection_name", sa.String(length=120), nullable=True)
    )
    bind = op.get_bind()
    bind.execute(
        sa.text(
            "UPDATE saved_requests SET collection_name = "
            "(SELECT name FROM collections WHERE collections.id = saved_requests.collection_id)"
        )
    )
    op.drop_index("ix_saved_requests_collection_id", table_name="saved_requests")
    with op.batch_alter_table("saved_requests") as batch_op:
        batch_op.drop_constraint("fk_saved_requests_collection_id_collections", type_="foreignkey")
        batch_op.drop_column("collection_id")
    op.drop_index("ix_collections_project_id", table_name="collections")
    op.drop_table("collections")
    op.create_index("ix_saved_requests_collection_name", "saved_requests", ["collection_name"])
