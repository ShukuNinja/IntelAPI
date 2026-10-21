from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, String, func, true
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class HealthCheck(Base):
    __tablename__ = "health_checks"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    project_id: Mapped[UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="RESTRICT"), nullable=False
    )
    saved_request_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("saved_requests.id", ondelete="SET NULL"), nullable=True
    )
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    definition: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    enabled: Mapped[bool] = mapped_column(
        Boolean, default=True, server_default=true(), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    __table_args__ = (
        Index(
            "ix_health_checks_project_enabled_updated", "project_id", "enabled", updated_at.desc()
        ),
    )


class AssertionResult(Base):
    __tablename__ = "assertion_results"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    execution_id: Mapped[UUID] = mapped_column(
        ForeignKey("executions.id", ondelete="CASCADE"), nullable=False
    )
    health_check_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("health_checks.id", ondelete="SET NULL"), nullable=True
    )
    assertion_type: Mapped[str] = mapped_column(String(32), nullable=False)
    passed: Mapped[bool] = mapped_column(Boolean, nullable=False)
    expected: Mapped[Any | None] = mapped_column(JSONB, nullable=True)
    actual: Mapped[Any | None] = mapped_column(JSONB, nullable=True)
    message: Mapped[str] = mapped_column(String(2000), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        Index("ix_assertion_results_execution", "execution_id"),
        Index("ix_assertion_results_health_created", "health_check_id", created_at.desc()),
    )
