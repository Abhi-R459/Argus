"""Append-only review decisions for suspicious-activity flags."""

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class SuspiciousActivityReview(Base):
    """Immutable review or reopen event associated with a risk flag."""

    __tablename__ = "suspicious_activity_reviews"

    review_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    flag_id: Mapped[int] = mapped_column(
        ForeignKey("suspicious_activity_flags.flag_id"), nullable=False
    )
    reviewer_user_id: Mapped[int] = mapped_column(
        ForeignKey("users.user_id"), nullable=False
    )
    action: Mapped[str] = mapped_column(String(16), nullable=False)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
