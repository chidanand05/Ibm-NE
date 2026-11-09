"""ActionPlanApproval ORM model — table: action_plan_approvals."""

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.db.base import Base, new_uuid


class ActionPlanApproval(Base):
    __tablename__ = "action_plan_approvals"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=new_uuid)
    plan_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("action_plans.id"), nullable=False, index=True
    )
    officer_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("users.id"), nullable=False, index=True
    )

    # APPROVED | REJECTED | SENT_BACK
    decision: Mapped[str] = mapped_column(String, nullable=False)

    comments: Mapped[str | None] = mapped_column(Text, nullable=True)
    edits_made: Mapped[dict | None] = mapped_column(JSONB, nullable=True)  # diff of officer changes
    ip_address: Mapped[str | None] = mapped_column(String, nullable=True)

    approved_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Relationships
    plan = relationship("ActionPlan", back_populates="approvals")
    officer = relationship("User", back_populates="approvals")
