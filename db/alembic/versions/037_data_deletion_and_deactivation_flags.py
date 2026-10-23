"""Flag any audited deletion and bursts of employee deactivation.

Revision ID: 037_data_deletion_and_deactivation_flags
Revises: 036_bound_account_role
"""

from alembic import op


revision = "037_data_deletion_and_deactivation_flags"
down_revision = "036_bound_account_role"
branch_labels = None
depends_on = None


def upgrade():
    # Preserve existing flag/review rows while updating the legacy rule name.
    op.execute("""
        UPDATE public.suspicious_activity_flags
        SET flag_reason = 'data_deletion'
        WHERE flag_reason = 'mass_employee_deletions'
    """)

    op.execute("""
        CREATE OR REPLACE PROCEDURE public.refresh_suspicious_activity_flags()
        LANGUAGE plpgsql
        SECURITY DEFINER
        SET search_path = pg_catalog, public, pg_temp
        AS $$
        BEGIN
            -- Flag each salary change whose absolute difference is over 30%.
            WITH salary_changes AS (
                SELECT
                    sequence_id,
                    COALESCE(employee_id, (new_value->>'employee_id')::INT) AS emp_id,
                    (new_value->>'amount')::NUMERIC AS current_salary,
                    LAG((new_value->>'amount')::NUMERIC) OVER (
                        PARTITION BY COALESCE(employee_id, (new_value->>'employee_id')::INT)
                        ORDER BY sequence_id ASC
                    ) AS prev_salary
                FROM public.audit_log
                WHERE table_name = 'salary_history'
                  AND action = 'INSERT'
            )
            INSERT INTO public.suspicious_activity_flags (audit_log_sequence_id, flag_reason)
            SELECT sc.sequence_id, 'salary_change_exceeds_30_percent'
            FROM salary_changes sc
            WHERE sc.prev_salary IS NOT NULL
              AND sc.prev_salary > 0
              AND ABS(sc.current_salary - sc.prev_salary) / sc.prev_salary > 0.30
              AND NOT EXISTS (
                  SELECT 1 FROM public.suspicious_activity_flags saf
                  WHERE saf.audit_log_sequence_id = sc.sequence_id
              );

            -- Every committed DELETE recorded in the audit log is a data deletion.
            INSERT INTO public.suspicious_activity_flags (audit_log_sequence_id, flag_reason)
            SELECT al.sequence_id, 'data_deletion'
            FROM public.audit_log al
            WHERE al.action = 'DELETE'
              AND NOT EXISTS (
                  SELECT 1 FROM public.suspicious_activity_flags saf
                  WHERE saf.audit_log_sequence_id = al.sequence_id
              );

            -- A burst is more than three (four or more) employee deactivations
            -- in any forward-looking rolling one-hour window. Flag the event(s)
            -- at the start of qualifying windows; repeated calls are idempotent.
            WITH deactivation_events AS (
                SELECT sequence_id, created_at
                FROM public.audit_log
                WHERE table_name = 'employees'
                  AND action = 'UPDATE'
                  AND old_value->>'is_active' = 'true'
                  AND new_value->>'is_active' = 'false'
            ), qualifying_events AS (
                SELECT sequence_id
                FROM (
                    SELECT sequence_id,
                           COUNT(*) OVER (
                               ORDER BY created_at
                               RANGE BETWEEN CURRENT ROW AND INTERVAL '1 hour' FOLLOWING
                           ) AS events_in_next_hour
                    FROM deactivation_events
                ) counted
                WHERE events_in_next_hour > 3
            )
            INSERT INTO public.suspicious_activity_flags (audit_log_sequence_id, flag_reason)
            SELECT qe.sequence_id, 'mass_employee_deactivations'
            FROM qualifying_events qe
            WHERE NOT EXISTS (
                SELECT 1 FROM public.suspicious_activity_flags saf
                WHERE saf.audit_log_sequence_id = qe.sequence_id
            );
        END;
        $$
    """)


def downgrade():
    raise RuntimeError(
        "Detection rule changes are forward-only; keep deletion and deactivation evidence intact."
    )
