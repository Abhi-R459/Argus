from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, LargeBinary, String, func
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class HrUndoAction(Base):
    __tablename__ = "hr_undo_actions"

    action_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    employee_id: Mapped[int] = mapped_column(ForeignKey("employees.employee_id"), nullable=False)
    action_type: Mapped[str] = mapped_column(String(32), nullable=False)
    actor_user_id: Mapped[int] = mapped_column(ForeignKey("users.user_id"), nullable=False)
    before_ciphertext: Mapped[bytes | None] = mapped_column(LargeBinary)
    after_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    undone_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    undone_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.user_id"))
