from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import String, Boolean, CheckConstraint, DateTime, func
from datetime import datetime
from typing import List

from .base import Base

class User(Base):
    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint("role IN ('hr_admin', 'compliance_auditor')", name="users_role_check"),
    )

    user_id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    clerk_user_id: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    role: Mapped[str] = mapped_column(String(50), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())

    audit_logs_actor: Mapped[List["AuditLog"]] = relationship("AuditLog", back_populates="actor", foreign_keys="AuditLog.actor_user_id")
    reviewed_flags: Mapped[List["SuspiciousActivityFlag"]] = relationship("SuspiciousActivityFlag", back_populates="reviewer")

    def __repr__(self) -> str:
        return f"<User(user_id={self.user_id}, clerk_user_id='{self.clerk_user_id}', role='{self.role}')>"
