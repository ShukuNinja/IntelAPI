from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class FindingTriageRecord(Base):
    __tablename__ = "finding_triage"
    __table_args__ = (
        UniqueConstraint("execution_report_id", "evidence_key", name="uq_finding_triage_evidence"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    project_id: Mapped[UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    execution_report_id: Mapped[UUID] = mapped_column(
        ForeignKey("execution_reports.id", ondelete="CASCADE"), nullable=False, index=True
    )
    evidence_key: Mapped[str] = mapped_column(String(96), nullable=False)
    classification: Mapped[str] = mapped_column(String(32), nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
