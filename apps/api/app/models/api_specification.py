from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, Index, Numeric, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class APISpecification(Base):
    __tablename__ = "api_specifications"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    project_id: Mapped[UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="RESTRICT"), nullable=False
    )
    created_by_user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    source_kind: Mapped[str] = mapped_column(String(16), nullable=False)
    source_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    spec_document: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    content_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    spec_version: Mapped[int] = mapped_column(default=1, nullable=False)
    openapi_version: Mapped[str | None] = mapped_column(String(32), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        UniqueConstraint("project_id", "content_sha256", name="uq_api_specs_project_hash"),
        Index("ix_api_specs_project_created", "project_id", created_at.desc()),
    )


class APIOperation(Base):
    __tablename__ = "api_operations"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    specification_id: Mapped[UUID] = mapped_column(
        ForeignKey("api_specifications.id", ondelete="CASCADE"), nullable=False
    )
    operation_key: Mapped[str] = mapped_column(String(255), nullable=False)
    method: Mapped[str] = mapped_column(String(12), nullable=False)
    path_template: Mapped[str] = mapped_column(Text, nullable=False)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    operation_document: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        UniqueConstraint("specification_id", "operation_key", name="uq_api_operations_spec_key"),
        Index("ix_api_operations_spec_path", "specification_id", "path_template"),
    )


class KnowledgeFact(Base):
    __tablename__ = "knowledge_facts"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    project_id: Mapped[UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="RESTRICT"), nullable=False
    )
    specification_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("api_specifications.id", ondelete="SET NULL"), nullable=True
    )
    operation_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("api_operations.id", ondelete="SET NULL"), nullable=True
    )
    execution_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("executions.id", ondelete="SET NULL"), nullable=True
    )
    fact_type: Mapped[str] = mapped_column(String(80), nullable=False)
    subject: Mapped[str] = mapped_column(String(255), nullable=False)
    fact_value: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    provenance: Mapped[str] = mapped_column(String(16), nullable=False)
    confidence: Mapped[Decimal | None] = mapped_column(Numeric(4, 3), nullable=True)
    source_ref: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        Index(
            "ix_knowledge_facts_project_operation_type", "project_id", "operation_id", "fact_type"
        ),
    )
