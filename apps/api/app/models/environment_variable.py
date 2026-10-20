from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    LargeBinary,
    String,
    Text,
    UniqueConstraint,
    false,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class EnvironmentVariable(Base):
    """A plain or encrypted variable belonging to an environment."""

    __tablename__ = "environment_variables"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)

    environment_id: Mapped[UUID] = mapped_column(
        ForeignKey("environments.id", ondelete="CASCADE"),
        nullable=False,
    )

    key: Mapped[str] = mapped_column(String(160), nullable=False)

    # Secret values are ciphertext; non-secret values use value_plain.
    # Neither value is exposed directly by a public response DTO.
    value_ciphertext: Mapped[bytes | None] = mapped_column(
        LargeBinary,
        nullable=True,
    )
    value_plain: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    is_secret: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default=false(),
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    __table_args__ = (
        UniqueConstraint(
            "environment_id",
            "key",
            name="uq_environment_variables_environment_key",
        ),
        CheckConstraint(
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
        CheckConstraint(
            "NOT is_secret OR value_ciphertext IS NOT NULL",
            name="ck_environment_variables_secret_encrypted",
        ),
        Index(
            "ix_environment_variables_environment",
            "environment_id",
        ),
    )
