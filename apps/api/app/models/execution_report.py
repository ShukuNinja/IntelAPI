from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import JSON, DateTime, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class ExecutionReportRecord(Base):
    __tablename__ = "execution_reports"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    project_id: Mapped[UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    specification_id: Mapped[UUID] = mapped_column(
        ForeignKey("api_specifications.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    execution_id: Mapped[UUID] = mapped_column(
        ForeignKey("executions.id", ondelete="RESTRICT"), nullable=False, unique=True
    )
    candidate_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    report: Mapped[dict] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
