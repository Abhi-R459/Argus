from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import Numeric, ForeignKey, DateTime, Date, UniqueConstraint, CheckConstraint, func
from datetime import datetime, date
from decimal import Decimal

from .base import Base

class SalaryHistory(Base):
    __tablename__ = "salary_history"
    __table_args__ = (
        CheckConstraint("amount > 0", name="salary_history_amount_check"),
        UniqueConstraint("employee_id", "effective_date", name="uq_employee_salary_date"),
    )

    salary_history_id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    employee_id: Mapped[int] = mapped_column(ForeignKey("employees.employee_id"), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    effective_date: Mapped[date] = mapped_column(Date, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())

    employee: Mapped["Employee"] = relationship("Employee", back_populates="salary_history")

    def __repr__(self) -> str:
        return f"<SalaryHistory(salary_history_id={self.salary_history_id}, employee_id={self.employee_id})>"
