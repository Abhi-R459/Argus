"""DB-001: Create Core Entity Tables

Revision ID: 001_core_entity_tables
Revises: 
Create Date: 2026-07-25 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '001_core_entity_tables'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Supabase grants its Data API roles access to newly created public objects
    # by default. Argus uses Clerk and private PostgreSQL roles, so remove those
    # defaults before creating any objects. Stock PostgreSQL without these
    # Supabase roles remains supported.
    if op.get_bind().dialect.name == "postgresql":
        op.execute("""
        DO $$
        DECLARE
            v_owner NAME := current_user;
            v_role NAME;
        BEGIN
            REVOKE USAGE, CREATE ON SCHEMA public FROM PUBLIC;
            FOR v_role IN
                SELECT rolname FROM pg_roles
                WHERE rolname IN ('anon', 'authenticated', 'service_role')
            LOOP
                EXECUTE format('REVOKE USAGE, CREATE ON SCHEMA public FROM %I', v_role);
                EXECUTE format(
                    'ALTER DEFAULT PRIVILEGES FOR ROLE %I IN SCHEMA public REVOKE ALL ON TABLES FROM %I',
                    v_owner, v_role
                );
                EXECUTE format(
                    'ALTER DEFAULT PRIVILEGES FOR ROLE %I IN SCHEMA public REVOKE ALL ON SEQUENCES FROM %I',
                    v_owner, v_role
                );
                EXECUTE format(
                    'ALTER DEFAULT PRIVILEGES FOR ROLE %I IN SCHEMA public REVOKE EXECUTE ON ROUTINES FROM %I',
                    v_owner, v_role
                );
            END LOOP;
            -- PostgreSQL grants routine execution to PUBLIC by default. This
            -- global revoke is required because schema-level revokes cannot
            -- subtract privileges granted by the global default ACL.
            EXECUTE format(
                'ALTER DEFAULT PRIVILEGES FOR ROLE %I REVOKE EXECUTE ON ROUTINES FROM PUBLIC',
                v_owner
            );
        END $$;
        """)

    # 1. Departments Table
    op.create_table(
        'departments',
        sa.Column('department_id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.PrimaryKeyConstraint('department_id'),
        sa.UniqueConstraint('name', name='uq_departments_name')
    )

    # 2. Roles Table
    op.create_table(
        'roles',
        sa.Column('role_id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('title', sa.String(length=255), nullable=False),
        sa.Column('department_id', sa.Integer(), nullable=False),
        sa.Column('salary_band_min', sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column('salary_band_max', sa.Numeric(precision=12, scale=2), nullable=False),
        sa.CheckConstraint('salary_band_min <= salary_band_max', name='chk_salary_band'),
        sa.ForeignKeyConstraint(['department_id'], ['departments.department_id'], name='fk_roles_department_id'),
        sa.PrimaryKeyConstraint('role_id')
    )

    # 3. Users Table
    op.create_table(
        'users',
        sa.Column('user_id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('clerk_user_id', sa.String(length=255), nullable=False),
        sa.Column('full_name', sa.String(length=255), nullable=False),
        sa.Column('email', sa.String(length=255), nullable=False),
        sa.Column('role', sa.String(length=50), nullable=False),
        sa.Column('is_active', sa.Boolean(), server_default=sa.text('true'), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.CheckConstraint("role IN ('hr_admin', 'compliance_auditor')", name='chk_users_role'),
        sa.PrimaryKeyConstraint('user_id'),
        sa.UniqueConstraint('clerk_user_id', name='uq_users_clerk_user_id'),
        sa.UniqueConstraint('email', name='uq_users_email')
    )

    # 4. Employees Table
    op.create_table(
        'employees',
        sa.Column('employee_id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('full_name', sa.String(length=255), nullable=False),
        sa.Column('email', sa.String(length=255), nullable=False),
        sa.Column('role_id', sa.Integer(), nullable=False),
        sa.Column('national_id_encrypted', sa.LargeBinary(), nullable=False),
        sa.Column('contact_info_encrypted', sa.LargeBinary(), nullable=False),
        sa.Column('date_hired', sa.Date(), nullable=False),
        sa.Column('is_active', sa.Boolean(), server_default=sa.text('true'), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.ForeignKeyConstraint(['role_id'], ['roles.role_id'], name='fk_employees_role_id'),
        sa.PrimaryKeyConstraint('employee_id'),
        sa.UniqueConstraint('email', name='uq_employees_email')
    )

    # 5. Salary History Table
    op.create_table(
        'salary_history',
        sa.Column('salary_history_id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('employee_id', sa.Integer(), nullable=False),
        sa.Column('amount', sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column('effective_date', sa.Date(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.CheckConstraint('amount > 0', name='chk_salary_history_amount'),
        sa.ForeignKeyConstraint(['employee_id'], ['employees.employee_id'], name='fk_salary_history_employee_id'),
        sa.PrimaryKeyConstraint('salary_history_id'),
        sa.UniqueConstraint('employee_id', 'effective_date', name='uq_employee_salary_date')
    )


def downgrade() -> None:
    # Drop in reverse dependency order
    op.drop_table('salary_history')
    op.drop_table('employees')
    op.drop_table('users')
    op.drop_table('roles')
    op.drop_table('departments')
