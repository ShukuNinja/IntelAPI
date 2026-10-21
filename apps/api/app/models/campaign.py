"""Durable campaign, test-case, job, and event records."""

from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import (
    BigInteger,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Campaign(Base):
    __tablename__ = "campaigns"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    project_id: Mapped[UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="RESTRICT"), nullable=False
    )
    created_by_user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    state: Mapped[str] = mapped_column(String(16), nullable=False, default="queued")
    configuration: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    budget_max_executions: Mapped[int] = mapped_column(Integer, nullable=False)
    budget_max_iterations: Mapped[int] = mapped_column(Integer, nullable=False)
    budget_max_duration_seconds: Mapped[int] = mapped_column(Integer, nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    cancel_requested_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    failure_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    failure_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    __table_args__ = (
        Index("ix_campaigns_project_created", "project_id", created_at.desc()),
        Index("ix_campaigns_state_created", "state", "created_at"),
    )


class TestCase(Base):
    __tablename__ = "test_cases"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    project_id: Mapped[UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="RESTRICT"), nullable=False
    )
    campaign_id: Mapped[UUID] = mapped_column(
        ForeignKey("campaigns.id", ondelete="CASCADE"), nullable=False
    )
    operation_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("api_operations.id", ondelete="SET NULL"), nullable=True
    )
    candidate_key: Mapped[str] = mapped_column(String(255), nullable=False)
    category: Mapped[str] = mapped_column(String(32), nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    request_override: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    expected_behavior: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    generation_provenance: Mapped[str] = mapped_column(String(16), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        UniqueConstraint("campaign_id", "candidate_key", name="uq_test_cases_campaign_candidate"),
        Index("ix_test_cases_campaign_created", "campaign_id", "created_at"),
    )


class CampaignJob(Base):
    __tablename__ = "campaign_jobs"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    campaign_id: Mapped[UUID] = mapped_column(
        ForeignKey("campaigns.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    state: Mapped[str] = mapped_column(String(16), nullable=False, default="queued")
    available_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    lease_owner: Mapped[str | None] = mapped_column(String(160), nullable=True)
    lease_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    attempt_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_error_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    __table_args__ = (
        Index("ix_campaign_jobs_state_available", "state", "available_at"),
        Index("ix_campaign_jobs_lease", "lease_expires_at"),
    )


class CampaignEvent(Base):
    __tablename__ = "campaign_events"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    campaign_id: Mapped[UUID] = mapped_column(
        ForeignKey("campaigns.id", ondelete="CASCADE"), nullable=False
    )
    sequence_number: Mapped[int] = mapped_column(BigInteger, nullable=False)
    event_type: Mapped[str] = mapped_column(String(80), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        UniqueConstraint("campaign_id", "sequence_number", name="uq_campaign_events_sequence"),
        Index("ix_campaign_events_campaign_created", "campaign_id", "created_at"),
    )
