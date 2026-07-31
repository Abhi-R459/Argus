from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import String
from typing import List

from .base import Base

class Department(Base):
    __tablename__ = "departments"

    department_id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)

    roles: Mapped[List["Role"]] = relationship("Role", back_populates="department")

    def __repr__(self) -> str:
        return f"<Department(department_id={self.department_id}, name='{self.name}')>"
