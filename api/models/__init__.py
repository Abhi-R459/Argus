from .base import Base
from .department import Department
from .role import Role
from .user import User
from .employee import Employee
from .salary_history import SalaryHistory
from .audit_log import AuditLog
from .suspicious_activity_flag import SuspiciousActivityFlag

__all__ = [
    "Base",
    "Department",
    "Role",
    "User",
    "Employee",
    "SalaryHistory",
    "AuditLog",
    "SuspiciousActivityFlag",
]
