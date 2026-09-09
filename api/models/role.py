from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import String, Numeric, ForeignKey, CheckConstraint
from typing import List
from decimal import Decimal

from .base import Base

class Role(Base):
    __tablename__ = "roles"
    __table_args__ = (
        CheckConstraint("salary_band_min <= salary_band_max", name="chk_salary_band"),
    )

    role_id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    department_id: Mapped[int] = mapped_column(ForeignKey("departments.department_id"), nullable=False)
    salary_band_min: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    salary_band_max: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)

    department: Mapped["Department"] = relationship("Department", back_populates="roles")
    employees: Mapped[List["Employee"]] = relationship("Employee", back_populates="role")

    def __repr__(self) -> str:
        return f"<Role(role_id={self.role_id}, title='{self.title}')>"
