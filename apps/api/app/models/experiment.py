"""Persisted experiments and their independently executed approach runs."""

from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, Index, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Experiment(Base):
    __tablename__ = "experiments"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    project_id: Mapped[UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="RESTRICT"), nullable=False
    )
    created_by_user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    specification_id: Mapped[UUID] = mapped_column(
        ForeignKey("api_specifications.id", ondelete="RESTRICT"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    configuration: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    __table_args__ = (Index("ix_experiments_project_created", "project_id", created_at.desc()),)


class ExperimentRun(Base):
    __tablename__ = "experiment_runs"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    experiment_id: Mapped[UUID] = mapped_column(
        ForeignKey("experiments.id", ondelete="CASCADE"), nullable=False
    )
    campaign_id: Mapped[UUID] = mapped_column(
        ForeignKey("campaigns.id", ondelete="RESTRICT"), nullable=False
    )
    approach: Mapped[str] = mapped_column(String(32), nullable=False)
    configuration: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    generation_metadata: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        UniqueConstraint("campaign_id", name="uq_experiment_runs_campaign"),
        UniqueConstraint("experiment_id", "approach", name="uq_experiment_runs_approach"),
        Index("ix_experiment_runs_experiment", "experiment_id", "created_at"),
    )
