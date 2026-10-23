"""Enforce salary bands for employee and salary-history writes.

Revision ID: 038_salary_band_enforcement
Revises: 037_data_delete_deactivate
"""

from alembic import op


revision = "038_salary_band_enforcement"
down_revision = "037_data_delete_deactivate"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""
        CREATE FUNCTION public.argus_enforce_role_salary_band() RETURNS trigger
        LANGUAGE plpgsql
        SET search_path = pg_catalog, public, pg_temp
        AS $$
        DECLARE
            assigned_role_id INTEGER;
            band_min NUMERIC(12, 2);
            band_max NUMERIC(12, 2);
            current_salary NUMERIC(12, 2);
            violating_employee_id INTEGER;
            violating_salary NUMERIC(12, 2);
        BEGIN
            IF TG_TABLE_NAME = 'salary_history' THEN
                -- Serialize salary writes with employee role changes and role-band
                -- edits so a concurrent change cannot bypass the policy.
                SELECT role_id INTO assigned_role_id
                FROM public.employees
                WHERE employee_id = NEW.employee_id
                FOR SHARE;

                IF NOT FOUND THEN
                    RETURN NEW; -- The employee FK reports the missing parent.
                END IF;

                SELECT salary_band_min, salary_band_max
                  INTO band_min, band_max
                FROM public.roles
                WHERE role_id = assigned_role_id
                FOR SHARE;

                IF FOUND AND (NEW.amount < band_min OR NEW.amount > band_max) THEN
                    RAISE EXCEPTION
                        'Salary % is outside role % annual band [%–%] INR',
                        NEW.amount, assigned_role_id, band_min, band_max
                        USING ERRCODE = '23514', CONSTRAINT = 'salary_within_role_band';
                END IF;
                RETURN NEW;
            END IF;

            IF TG_TABLE_NAME = 'employees' THEN
                IF NEW.role_id IS NOT DISTINCT FROM OLD.role_id THEN
                    RETURN NEW;
                END IF;

                SELECT salary_band_min, salary_band_max
                  INTO band_min, band_max
                FROM public.roles
                WHERE role_id = NEW.role_id
                FOR SHARE;

                IF NOT FOUND THEN
                    RETURN NEW; -- The employee FK reports the missing parent.
                END IF;

                SELECT amount INTO current_salary
                FROM public.salary_history
                WHERE employee_id = NEW.employee_id
                ORDER BY effective_date DESC, salary_history_id DESC
                LIMIT 1;

                IF current_salary IS NOT NULL
                   AND (current_salary < band_min OR current_salary > band_max) THEN
                    RAISE EXCEPTION
                        'Current salary % is outside role % annual band [%–%] INR',
                        current_salary, NEW.role_id, band_min, band_max
                        USING ERRCODE = '23514', CONSTRAINT = 'salary_within_role_band';
                END IF;
                RETURN NEW;
            END IF;

            IF TG_TABLE_NAME = 'roles' THEN
                IF NEW.salary_band_min IS NOT DISTINCT FROM OLD.salary_band_min
                   AND NEW.salary_band_max IS NOT DISTINCT FROM OLD.salary_band_max THEN
                    RETURN NEW;
                END IF;

                SELECT employee.employee_id, latest.amount
                  INTO violating_employee_id, violating_salary
                FROM public.employees AS employee
                JOIN LATERAL (
                    SELECT history.amount
                    FROM public.salary_history AS history
                    WHERE history.employee_id = employee.employee_id
                    ORDER BY history.effective_date DESC, history.salary_history_id DESC
                    LIMIT 1
                ) AS latest ON TRUE
                WHERE employee.role_id = NEW.role_id
                  AND (latest.amount < NEW.salary_band_min OR latest.amount > NEW.salary_band_max)
                LIMIT 1;

                IF FOUND THEN
                    RAISE EXCEPTION
                        'Role band update would put employee % salary % outside the new band [%–%] INR',
                        violating_employee_id, violating_salary,
                        NEW.salary_band_min, NEW.salary_band_max
                        USING ERRCODE = '23514', CONSTRAINT = 'salary_within_role_band';
                END IF;
                RETURN NEW;
            END IF;

            RETURN NEW;
        END;
        $$
    """)
    op.execute("""
        REVOKE ALL ON FUNCTION public.argus_enforce_role_salary_band() FROM PUBLIC;
        CREATE TRIGGER enforce_salary_history_role_band
            BEFORE INSERT OR UPDATE OF employee_id, amount, effective_date ON public.salary_history
            FOR EACH ROW EXECUTE FUNCTION public.argus_enforce_role_salary_band();
        CREATE TRIGGER enforce_employee_role_salary_band
            BEFORE UPDATE OF role_id ON public.employees
            FOR EACH ROW EXECUTE FUNCTION public.argus_enforce_role_salary_band();
        CREATE TRIGGER enforce_role_band_for_existing_employees
            BEFORE UPDATE OF salary_band_min, salary_band_max ON public.roles
            FOR EACH ROW EXECUTE FUNCTION public.argus_enforce_role_salary_band();
    """)


def downgrade():
    op.execute("DROP TRIGGER IF EXISTS enforce_role_band_for_existing_employees ON public.roles")
    op.execute("DROP TRIGGER IF EXISTS enforce_employee_role_salary_band ON public.employees")
    op.execute("DROP TRIGGER IF EXISTS enforce_salary_history_role_band ON public.salary_history")
    op.execute("DROP FUNCTION IF EXISTS public.argus_enforce_role_salary_band()")
