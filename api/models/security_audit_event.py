"""Durable, privacy-preserving events for auditor security actions."""

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class SecurityAuditEvent(Base):
    """Append-only metadata for sensitive auditor queries."""

    __tablename__ = "security_audit_events"

    event_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    actor_user_id: Mapped[int] = mapped_column(Integer, nullable=False)
    actor_email: Mapped[str] = mapped_column(String(255), nullable=False)
    blind_index: Mapped[str | None] = mapped_column(String(64), nullable=True)
    employee_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    sequence_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    matches_found: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    client_ip: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
