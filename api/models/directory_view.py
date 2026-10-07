"""SQLAlchemy mapping for the v_employee_directory view.

Provides sanitized, PII-shielded employee metadata for least-privilege
database roles (such as compliance_auditor).
"""

from datetime import date, datetime
from decimal import Decimal
from typing import Optional
from sqlalchemy import Integer, String, Boolean, Date, DateTime, Numeric
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class EmployeeDirectoryView(Base):
    """Sanitized view of employee directory joining roles and departments.

    Maps to PostgreSQL view `v_compliance_employee_directory`, which contains
    masked name and email values for direct compliance-auditor DB access.
    """

    __tablename__ = "v_compliance_employee_directory"
    __table_args__ = {"info": dict(is_view=True), "extend_existing": True}

    employee_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    full_name: Mapped[str] = mapped_column(String(255))
    email: Mapped[str] = mapped_column(String(255))
    role_title: Mapped[str] = mapped_column(String(100))
    department_name: Mapped[str] = mapped_column(String(100))
    salary_band_min: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 2), nullable=True)
    salary_band_max: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 2), nullable=True)
    date_hired: Mapped[date] = mapped_column(Date)
    is_active: Mapped[bool] = mapped_column(Boolean)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    def __repr__(self) -> str:
        return f"<EmployeeDirectoryView(id={self.employee_id}, name={self.full_name!r})>"
