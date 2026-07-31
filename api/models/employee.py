from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import String, Boolean, ForeignKey, DateTime, Date, LargeBinary, func
from datetime import datetime, date
from typing import List

from .base import Base

class Employee(Base):
    __tablename__ = "employees"

    employee_id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    role_id: Mapped[int] = mapped_column(ForeignKey("roles.role_id"), nullable=False)
    national_id_encrypted: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    contact_info_encrypted: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    date_hired: Mapped[date] = mapped_column(Date, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())

    role: Mapped["Role"] = relationship("Role", back_populates="employees")
    salary_history: Mapped[List["SalaryHistory"]] = relationship("SalaryHistory", back_populates="employee")
    audit_logs: Mapped[List["AuditLog"]] = relationship("AuditLog", back_populates="employee", foreign_keys="AuditLog.employee_id")

    def __repr__(self) -> str:
        return f"<Employee(employee_id={self.employee_id}, email='{self.email}')>"
