from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import JSON, DateTime, ForeignKey, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class ApiSpecification(Base):
    __tablename__ = "api_specifications"
    __table_args__ = (UniqueConstraint("project_id", "content_hash", name="uq_spec_project_hash"),)

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    project_id: Mapped[UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    spec_version: Mapped[str] = mapped_column(String(32), nullable=False)
    source_format: Mapped[str] = mapped_column(String(8), nullable=False)
    source_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    source_document: Mapped[dict] = mapped_column(JSON, nullable=False)
    normalized_operations: Mapped[list] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
