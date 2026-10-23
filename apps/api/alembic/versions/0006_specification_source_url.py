"""Track redacted remote specification source URLs."""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0006_specification_source_url"
down_revision: str | None = "0005_generation_reports"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "api_specifications", sa.Column("source_url", sa.String(length=2048), nullable=True)
    )


def downgrade() -> None:
    op.drop_column("api_specifications", "source_url")
