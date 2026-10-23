from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import case, select, func
from sqlalchemy.exc import IntegrityError
from typing import List

from ..dependencies import get_current_user, get_db_session, require_role
from ..models.user import User
from ..models.employee import Employee
from ..models.role import Role
from ..models.department import Department
from ..models.audit_log import AuditLog
from ..models.suspicious_activity_flag import SuspiciousActivityFlag
from ..schemas.analytics import (
    DashboardStatsResponse,
    RecentActivityItem,
    DepartmentItem,
    RoleItem,
    DepartmentCreate,
    RoleCreate,
)

router = APIRouter(tags=["Dashboard & Metadata"])


@router.get("/dashboard/stats", response_model=DashboardStatsResponse)
async def get_dashboard_stats(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session, scope="function"),
):
    """Retrieve real-time summary statistics and recent activity for the HR Dashboard."""
    # 1. Active and total employees
    active_res = await session.execute(
        select(func.count()).select_from(Employee).where(Employee.is_active == True)
    )
    active_employees = int(active_res.scalar() or 0)

    total_emp_res = await session.execute(
        select(func.count()).select_from(Employee)
    )
    total_employees = int(total_emp_res.scalar() or 0)

    # 2. Total audit events
    audit_res = await session.execute(
        select(func.count()).select_from(AuditLog)
    )
    total_audit_events = int(audit_res.scalar() or 0)

    # 3. Unreviewed suspicious activity flags
    flags_res = await session.execute(
        select(func.count())
        .select_from(SuspiciousActivityFlag)
        .where(SuspiciousActivityFlag.reviewed_at.is_(None))
        .where(SuspiciousActivityFlag.superseded_by_flag_id.is_(None))
    )
    unreviewed_flags = int(flags_res.scalar() or 0)

    # 4. Recent activity (last 10 events)
    recent_query = (
        select(
            AuditLog.sequence_id,
            AuditLog.action,
            AuditLog.table_name,
            func.coalesce(
                func.nullif(func.nullif(func.trim(User.full_name), ""), "Unknown"),
                func.nullif(func.trim(User.email), ""),
                case(
                    (AuditLog.actor_user_id.is_(None), "System"),
                    else_=func.concat("unresolved_user#", AuditLog.actor_user_id),
                ),
            ).label("actor_name"),
            AuditLog.severity,
            AuditLog.created_at,
        )
        .outerjoin(User, AuditLog.actor_user_id == User.user_id)
        .order_by(AuditLog.sequence_id.desc())
        .limit(10)
    )
    recent_res = await session.execute(recent_query)
    recent_rows = recent_res.all()

    recent_activity = [
        RecentActivityItem(
            sequence_id=r[0],
            action=r[1],
            table_name=r[2],
            actor_name=r[3],
            severity=r[4],
            created_at=r[5],
        )
        for r in recent_rows
    ]

    return DashboardStatsResponse(
        total_employees=total_employees,
        active_employees=active_employees,
        total_audit_events=total_audit_events,
        unreviewed_flags=unreviewed_flags,
        recent_activity=recent_activity,
    )


@router.get("/departments", response_model=List[DepartmentItem])
async def list_departments(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session, scope="function"),
):
    """List all corporate departments for dynamic dropdown selection."""
    res = await session.execute(
        select(Department.department_id, Department.name).order_by(Department.name)
    )
    return [DepartmentItem(department_id=r[0], name=r[1]) for r in res.all()]


@router.get("/roles", response_model=List[RoleItem])
async def list_roles(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session, scope="function"),
):
    """List all roles with department names and salary bands for dynamic dropdown selection."""
    res = await session.execute(
        select(
            Role.role_id,
            Role.title,
            Role.department_id,
            Department.name.label("department_name"),
            Role.salary_band_min,
            Role.salary_band_max,
        )
        .join(Department, Role.department_id == Department.department_id)
        .order_by(Department.name, Role.title)
    )
    return [
        RoleItem(
            role_id=r[0],
            title=r[1],
            department_id=r[2],
            department_name=r[3],
            salary_band_min=r[4],
            salary_band_max=r[5],
            min_salary=r[4],
            max_salary=r[5],
        )
        for r in res.all()
    ]


@router.post("/departments", response_model=DepartmentItem, status_code=201,
             dependencies=[Depends(require_role(["hr_admin"]))])
async def create_department(data: DepartmentCreate, session: AsyncSession = Depends(get_db_session, scope="function")):
    department = Department(name=data.name)
    session.add(department)
    try:
        await session.flush()
    except IntegrityError as exc:
        raise HTTPException(status_code=409, detail="A department with this name already exists.") from exc
    return DepartmentItem(department_id=department.department_id, name=department.name)


@router.post("/roles", response_model=RoleItem, status_code=201,
             dependencies=[Depends(require_role(["hr_admin"]))])
async def create_job_role(data: RoleCreate, session: AsyncSession = Depends(get_db_session, scope="function")):
    result = await session.execute(select(Department).where(Department.department_id == data.department_id))
    department = result.scalar_one_or_none()
    if department is None:
        raise HTTPException(status_code=422, detail="Choose an existing department.")
    role = Role(**data.model_dump())
    session.add(role)
    await session.flush()
    return RoleItem(role_id=role.role_id, title=role.title, department_id=role.department_id,
                    department_name=department.name, salary_band_min=role.salary_band_min,
                    salary_band_max=role.salary_band_max)
