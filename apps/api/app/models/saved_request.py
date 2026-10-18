from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class SavedRequest(Base):
    """A persisted HTTP request definition owned by a project."""

    __tablename__ = "saved_requests"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)

    project_id: Mapped[UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="RESTRICT"),
        nullable=False,
    )
    collection_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("collections.id", ondelete="SET NULL"),
        nullable=True,
    )
    environment_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("environments.id", ondelete="SET NULL"),
        nullable=True,
    )

    name: Mapped[str] = mapped_column(String(160), nullable=False)
    method: Mapped[str] = mapped_column(String(12), nullable=False)
    url_template: Mapped[str] = mapped_column(Text, nullable=False)

    headers: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        server_default=text("'{}'::jsonb"),
    )
    query_params: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        server_default=text("'{}'::jsonb"),
    )
    body: Mapped[Any | None] = mapped_column(JSONB, nullable=True)
    body_type: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        server_default=text("'none'"),
    )

    # Store references to configured credentials, never plaintext secrets.
    auth_config: Mapped[dict[str, Any] | None] = mapped_column(
        JSONB,
        nullable=True,
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
        CheckConstraint(
            "body_type IN "
            "('none', 'json', 'text', 'form_urlencoded', 'multipart')",
            name="ck_saved_requests_body_type",
        ),
        Index(
            "ix_saved_requests_project_updated",
            "project_id",
            updated_at.desc(),
        ),
        Index("ix_saved_requests_collection", "collection_id"),
        Index("ix_saved_requests_environment", "environment_id"),
    )