from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import String, ForeignKey, DateTime, BigInteger, Integer, CheckConstraint, func, CHAR
from sqlalchemy.dialects.postgresql import JSONB
from datetime import datetime
from typing import Optional, List, Any, Dict

from .base import Base

class AuditLog(Base):
    __tablename__ = "audit_log"
    __table_args__ = (
        CheckConstraint("action IN ('INSERT', 'UPDATE', 'DELETE')", name="audit_log_action_check"),
        CheckConstraint("severity IN ('INFO', 'WARNING', 'CRITICAL')", name="audit_log_severity_check"),
    )

    sequence_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    actor_user_id: Mapped[int] = mapped_column(ForeignKey("users.user_id"), nullable=False)
    employee_id: Mapped[Optional[int]] = mapped_column(ForeignKey("employees.employee_id"), nullable=True)
    action: Mapped[str] = mapped_column(String(20), nullable=False)
    table_name: Mapped[str] = mapped_column(String(100), nullable=False)
    row_id: Mapped[int] = mapped_column(Integer, nullable=False)
    old_value: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSONB, nullable=True)
    new_value: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSONB, nullable=True)
    severity: Mapped[str] = mapped_column(String(20), nullable=False)
    entry_hash: Mapped[str] = mapped_column(CHAR(64), nullable=False)
    previous_hash: Mapped[str] = mapped_column(CHAR(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())

    actor: Mapped["User"] = relationship("User", back_populates="audit_logs_actor", foreign_keys=[actor_user_id])
    employee: Mapped[Optional["Employee"]] = relationship("Employee", back_populates="audit_logs", foreign_keys=[employee_id])
    suspicious_flags: Mapped[List["SuspiciousActivityFlag"]] = relationship("SuspiciousActivityFlag", back_populates="audit_log")

    def __repr__(self) -> str:
        return f"<AuditLog(sequence_id={self.sequence_id}, action='{self.action}', table_name='{self.table_name}')>"
