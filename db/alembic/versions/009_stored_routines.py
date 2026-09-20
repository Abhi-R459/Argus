"""DB-018 & DB-019: Create Stored Routines

Revision ID: 009_stored_routines
Revises: 008_finalize_permissions
Create Date: 2026-08-31 14:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '009_stored_routines'
down_revision: Union[str, None] = '008_finalize_permissions'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create stored routines: reconstruct_employee_state function and refresh_suspicious_activity_flags procedure."""
    # 1. DB-018: reconstruct_employee_state function
    op.execute(sa.text("""
CREATE OR REPLACE FUNCTION reconstruct_employee_state(
    p_employee_id INT,
    p_as_of TIMESTAMPTZ
) RETURNS JSONB
LANGUAGE plpgsql STABLE
AS $func$
DECLARE
    v_state JSONB := NULL;
    v_row RECORD;
BEGIN
    FOR v_row IN
        SELECT action, old_value, new_value
        FROM audit_log
        WHERE table_name = 'employees'
          AND row_id = p_employee_id
          AND created_at <= p_as_of
        ORDER BY sequence_id ASC
    LOOP
        CASE v_row.action
            WHEN 'INSERT' THEN
                v_state := v_row.new_value;
            WHEN 'UPDATE' THEN
                IF v_state IS NOT NULL THEN
                    v_state := v_state || v_row.new_value;
                ELSE
                    v_state := v_row.new_value;
                END IF;
            WHEN 'DELETE' THEN
                v_state := NULL;
        END CASE;
    END LOOP;
    RETURN v_state;
END;
$func$;
"""))

    # 2. DB-019: refresh_suspicious_activity_flags procedure
    op.execute(sa.text("""
CREATE OR REPLACE PROCEDURE refresh_suspicious_activity_flags()
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
BEGIN
    -- Pattern 1: Salary change > 30%
    WITH salary_changes AS (
        SELECT
            sequence_id,
            COALESCE(employee_id, (new_value->>'employee_id')::INT) AS emp_id,
            (new_value->>'amount')::NUMERIC AS current_salary,
            LAG((new_value->>'amount')::NUMERIC) OVER (
                PARTITION BY COALESCE(employee_id, (new_value->>'employee_id')::INT)
                ORDER BY sequence_id ASC
            ) AS prev_salary
        FROM audit_log
        WHERE table_name = 'salary_history'
          AND action = 'INSERT'
    )
    INSERT INTO suspicious_activity_flags (audit_log_sequence_id, flag_reason)
    SELECT
        sc.sequence_id,
        'salary_change_exceeds_30_percent'
    FROM salary_changes sc
    WHERE sc.prev_salary IS NOT NULL
      AND sc.prev_salary > 0
      AND ABS(sc.current_salary - sc.prev_salary) / sc.prev_salary > 0.30
      AND NOT EXISTS (
          SELECT 1
          FROM suspicious_activity_flags saf
          WHERE saf.audit_log_sequence_id = sc.sequence_id
      );

    -- Pattern 2: Mass deletions (3 or more DELETE actions on employees within any 1-hour window)
    WITH deletion_events AS (
        SELECT
            sequence_id,
            created_at,
            LAG(created_at, 2) OVER w AS lag2_created_at,
            LEAD(created_at, 2) OVER w AS lead2_created_at,
            LAG(created_at, 1) OVER w AS lag1_created_at,
            LEAD(created_at, 1) OVER w AS lead1_created_at
        FROM audit_log
        WHERE table_name = 'employees'
          AND action = 'DELETE'
        WINDOW w AS (ORDER BY created_at ASC, sequence_id ASC)
    )
    INSERT INTO suspicious_activity_flags (audit_log_sequence_id, flag_reason)
    SELECT
        de.sequence_id,
        'mass_employee_deletions'
    FROM deletion_events de
    WHERE (
        (de.lag2_created_at IS NOT NULL AND de.created_at - de.lag2_created_at <= INTERVAL '1 hour')
        OR (de.lead2_created_at IS NOT NULL AND de.lead2_created_at - de.created_at <= INTERVAL '1 hour')
        OR (de.lag1_created_at IS NOT NULL AND de.lead1_created_at IS NOT NULL AND de.lead1_created_at - de.lag1_created_at <= INTERVAL '1 hour')
    )
    AND NOT EXISTS (
        SELECT 1
        FROM suspicious_activity_flags saf
        WHERE saf.audit_log_sequence_id = de.sequence_id
    );
END;
$$;
"""))


def downgrade() -> None:
    """Drop stored routines: reconstruct_employee_state function and refresh_suspicious_activity_flags procedure."""
    op.execute(sa.text("DROP FUNCTION IF EXISTS reconstruct_employee_state(INT, TIMESTAMPTZ)"))
    op.execute(sa.text("DROP PROCEDURE IF EXISTS refresh_suspicious_activity_flags()"))
