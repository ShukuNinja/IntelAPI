"""Store environment secret values in an encrypted field."""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0011_environment_secrets"
down_revision: str | None = "0010_health_checks"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "environments",
        sa.Column("secret_variables", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
    )
    op.add_column(
        "environments",
        sa.Column("secrets_migrated", sa.Boolean(), nullable=False, server_default=sa.false()),
    )


def downgrade() -> None:
    op.drop_column("environments", "secrets_migrated")
    op.drop_column("environments", "secret_variables")
