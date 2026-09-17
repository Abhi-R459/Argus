"""Employee CRUD and Salary endpoints.

Implements:
- GET    /api/employees          — List with search + pagination
- POST   /api/employees          — Create (hr_admin only)
- PATCH  /api/employees/{id}     — Update (hr_admin only)
- DELETE /api/employees/{id}     — Soft-delete (hr_admin only)
- POST   /api/employees/{id}/salary — Add salary record (hr_admin only)
"""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, or_
from sqlalchemy.exc import IntegrityError
import math

from ..dependencies import get_current_user, require_role, get_db_session
from ..models.user import User
from ..models.employee import Employee
from ..models.role import Role
from ..models.department import Department
from ..models.salary_history import SalaryHistory
from ..models.directory_view import EmployeeDirectoryView
from ..schemas.employee import (
    EmployeeListItem, EmployeeCreate, EmployeeUpdate,
    EmployeeCreateResponse, EmployeeUpdateResponse, EmployeeDeactivateResponse,
)
from ..schemas.salary import SalaryCreate, SalaryCreateResponse
from ..schemas.common import PaginatedResponse

router = APIRouter(prefix="/employees", tags=["Employees"])


@router.get("", response_model=PaginatedResponse[EmployeeListItem])
async def list_employees(
    search: str = Query(None, description="Filter by name or email"),
    page: int = Query(1, ge=1, description="Page number"),
    limit: int = Query(20, ge=1, le=100, description="Items per page"),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
):
    """Retrieve the employee directory with search and pagination.

    Role-aware execution:
    - compliance_auditor: Queries sanitized `v_employee_directory` view to enforce
      PII shielding while granting access to active personnel for time-travel verification.
    - hr_admin: Queries `employees` joined to `roles` and `departments`.
    """
    if current_user.role == "compliance_auditor":
        latest_salary = (
            select(SalaryHistory.amount)
            .where(SalaryHistory.employee_id == EmployeeDirectoryView.employee_id)
            .order_by(SalaryHistory.effective_date.desc())
            .limit(1)
            .correlate(EmployeeDirectoryView)
            .scalar_subquery()
        )

        query = select(
            EmployeeDirectoryView.employee_id,
            EmployeeDirectoryView.full_name,
            EmployeeDirectoryView.email,
            EmployeeDirectoryView.role_title,
            EmployeeDirectoryView.department_name,
            latest_salary.label("salary"),
            EmployeeDirectoryView.date_hired,
            EmployeeDirectoryView.is_active,
        )

        if search:
            pattern = f"%{search}%"
            query = query.where(
                or_(
                    EmployeeDirectoryView.full_name.ilike(pattern),
                    EmployeeDirectoryView.email.ilike(pattern),
                )
            )

        count_query = select(func.count()).select_from(query.subquery())
        total = await session.scalar(count_query) or 0

        pages = math.ceil(total / limit) if total > 0 else 0
        query = query.order_by(EmployeeDirectoryView.employee_id).offset((page - 1) * limit).limit(limit)
        result = await session.execute(query)
        rows = result.all()

        items = [
            EmployeeListItem(
                employee_id=row.employee_id,
                full_name=row.full_name,
                email=row.email,
                role_title=row.role_title,
                department_name=row.department_name,
                salary=row.salary,
                date_hired=row.date_hired,
                is_active=row.is_active,
            )
            for row in rows
        ]

        return PaginatedResponse(items=items, total=total, page=page, pages=pages)

    # Subquery: latest salary per employee (hr_admin)
    latest_salary = (
        select(SalaryHistory.amount)
        .where(SalaryHistory.employee_id == Employee.employee_id)
        .order_by(SalaryHistory.effective_date.desc())
        .limit(1)
        .correlate(Employee)
        .scalar_subquery()
    )

    # Base query (hr_admin)
    query = (
        select(
            Employee.employee_id,
            Employee.full_name,
            Employee.email,
            Role.title.label("role_title"),
            Department.name.label("department_name"),
            latest_salary.label("salary"),
            Employee.date_hired,
            Employee.is_active,
        )
        .join(Role, Employee.role_id == Role.role_id)
        .join(Department, Role.department_id == Department.department_id)
    )

    # Search filter
    if search:
        pattern = f"%{search}%"
        query = query.where(
            or_(
                Employee.full_name.ilike(pattern),
                Employee.email.ilike(pattern),
            )
        )

    # Total count
    count_query = select(func.count()).select_from(query.subquery())
    total = await session.scalar(count_query) or 0

    # Paginate
    pages = math.ceil(total / limit) if total > 0 else 0
    query = query.order_by(Employee.employee_id).offset((page - 1) * limit).limit(limit)
    result = await session.execute(query)
    rows = result.all()

    items = [
        EmployeeListItem(
            employee_id=row.employee_id,
            full_name=row.full_name,
            email=row.email,
            role_title=row.role_title,
            department_name=row.department_name,
            salary=row.salary,
            date_hired=row.date_hired,
            is_active=row.is_active,
        )
        for row in rows
    ]

    return PaginatedResponse(items=items, total=total, page=page, pages=pages)


@router.post(
    "",
    response_model=EmployeeCreateResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_role(["hr_admin"]))],
)
async def create_employee(
    data: EmployeeCreate,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
):
    """Create a new employee record. HR Admin only.

    Also creates the initial salary_history record.
    Sensitive fields (national_id, contact_info) are encoded to bytes
    for storage — actual pgcrypto encryption will be handled by DB
    triggers once Abhinav's Week 4 work lands.
    """
    # Verify role_id exists
    role_result = await session.execute(
        select(Role).where(Role.role_id == data.role_id)
    )
    if role_result.scalar_one_or_none() is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Role with id {data.role_id} does not exist.",
        )

    # Check for duplicate email
    email_result = await session.execute(
        select(Employee).where(Employee.email == data.email)
    )
    if email_result.scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An employee with this email already exists.",
        )

    # Encode sensitive fields to bytes (placeholder for pgcrypto)
    national_id_bytes = data.national_id.encode("utf-8")
    contact_info_bytes = data.contact_info.encode("utf-8")

    new_employee = Employee(
        full_name=data.full_name,
        email=data.email,
        role_id=data.role_id,
        national_id_encrypted=national_id_bytes,
        contact_info_encrypted=contact_info_bytes,
        date_hired=data.date_hired,
        is_active=True,
    )
    session.add(new_employee)
    await session.flush()  # Get employee_id before creating salary record

    # Create initial salary record
    initial_salary = SalaryHistory(
        employee_id=new_employee.employee_id,
        amount=data.salary,
        effective_date=data.date_hired,
    )
    session.add(initial_salary)

    # Commit is handled by the get_db_session dependency
    await session.flush()
    await session.refresh(new_employee)

    return EmployeeCreateResponse(
        employee_id=new_employee.employee_id,
        full_name=new_employee.full_name,
        email=new_employee.email,
        role_id=new_employee.role_id,
        date_hired=new_employee.date_hired,
        is_active=new_employee.is_active,
    )


@router.patch(
    "/{employee_id}",
    response_model=EmployeeUpdateResponse,
    dependencies=[Depends(require_role(["hr_admin"]))],
)
async def update_employee(
    employee_id: int,
    data: EmployeeUpdate,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
):
    """Update an existing employee record. HR Admin only.

    Only fields present in the request body are updated.
    """
    result = await session.execute(
        select(Employee).where(Employee.employee_id == employee_id)
    )
    employee = result.scalar_one_or_none()

    if employee is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Employee with id {employee_id} not found.",
        )

    update_data = data.model_dump(exclude_unset=True)

    # Handle contact_info separately (encode to bytes)
    if "contact_info" in update_data:
        contact_info = update_data.pop("contact_info")
        if contact_info is not None:
            employee.contact_info_encrypted = contact_info.encode("utf-8")

    # Validate role_id if provided
    if "role_id" in update_data:
        role_result = await session.execute(
            select(Role).where(Role.role_id == update_data["role_id"])
        )
        if role_result.scalar_one_or_none() is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Role with id {update_data['role_id']} does not exist.",
            )

    # Apply remaining updates
    for key, value in update_data.items():
        setattr(employee, key, value)

    await session.flush()
    await session.refresh(employee)

    return EmployeeUpdateResponse(
        employee_id=employee.employee_id,
        full_name=employee.full_name,
        email=employee.email,
        role_id=employee.role_id,
        is_active=employee.is_active,
    )


@router.delete(
    "/{employee_id}",
    response_model=EmployeeDeactivateResponse,
    dependencies=[Depends(require_role(["hr_admin"]))],
)
async def deactivate_employee(
    employee_id: int,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
):
    """Soft-delete an employee record. HR Admin only.

    Sets is_active = false rather than removing the row, preserving
    audit_log foreign key integrity.
    """
    result = await session.execute(
        select(Employee).where(Employee.employee_id == employee_id)
    )
    employee = result.scalar_one_or_none()

    if employee is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Employee with id {employee_id} not found.",
        )

    employee.is_active = False
    await session.flush()

    return EmployeeDeactivateResponse(
        employee_id=employee.employee_id,
        is_active=employee.is_active,
    )


@router.post(
    "/{employee_id}/salary",
    response_model=SalaryCreateResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_role(["hr_admin"]))],
)
async def add_salary_record(
    employee_id: int,
    data: SalaryCreate,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
):
    """Add a new salary record for an employee. HR Admin only.

    Business-rule enforcement (e.g., cannot decrease pay by >30%,
    cannot edit own salary) is handled by DB triggers once Abhinav's
    Week 4 work lands.
    """
    # Verify employee exists
    result = await session.execute(
        select(Employee).where(Employee.employee_id == employee_id)
    )
    employee = result.scalar_one_or_none()

    if employee is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Employee with id {employee_id} not found.",
        )

    new_salary = SalaryHistory(
        employee_id=employee_id,
        amount=data.amount,
        effective_date=data.effective_date,
    )

    try:
        session.add(new_salary)
        await session.flush()
        await session.refresh(new_salary)
    except IntegrityError:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"A salary record already exists for employee {employee_id} on {data.effective_date}.",
        )

    return SalaryCreateResponse(
        salary_history_id=new_salary.salary_history_id,
        employee_id=new_salary.employee_id,
        amount=new_salary.amount,
        effective_date=new_salary.effective_date,
    )
