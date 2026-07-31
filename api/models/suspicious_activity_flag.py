from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import String, ForeignKey, DateTime, BigInteger, func
from datetime import datetime
from typing import Optional

from .base import Base

class SuspiciousActivityFlag(Base):
    __tablename__ = "suspicious_activity_flags"

    flag_id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    audit_log_sequence_id: Mapped[int] = mapped_column(ForeignKey("audit_log.sequence_id"), nullable=False)
    reviewed_by_user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.user_id"), nullable=True)
    reviewed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    flag_reason: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())

    audit_log: Mapped["AuditLog"] = relationship("AuditLog", back_populates="suspicious_flags")
    reviewer: Mapped[Optional["User"]] = relationship("User", back_populates="reviewed_flags")

    def __repr__(self) -> str:
        return f"<SuspiciousActivityFlag(flag_id={self.flag_id}, reason='{self.flag_reason}')>"
