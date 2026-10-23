"""Group employee deactivation flags by incident instead of per audit row.

Revision ID: 039_group_deactivation_flags
Revises: 038_salary_band_enforcement
"""

from alembic import op
import sqlalchemy as sa


revision = "039_group_deactivation_flags"
down_revision = "038_salary_band_enforcement"
branch_labels = None
depends_on = None


_DEACTIVATION_CTES = """
    WITH deactivation_events AS (
        SELECT sequence_id, created_at
        FROM public.audit_log
        WHERE table_name = 'employees'
          AND action = 'UPDATE'
          AND old_value->>'is_active' = 'true'
          AND new_value->>'is_active' = 'false'
    ), qualifying_starts AS (
        SELECT sequence_id, created_at
        FROM (
            SELECT sequence_id, created_at,
                   COUNT(*) OVER (
                       ORDER BY created_at
                       RANGE BETWEEN CURRENT ROW AND INTERVAL '1 hour' FOLLOWING
                   ) AS events_in_next_hour
            FROM deactivation_events
        ) counted
        WHERE events_in_next_hour > 3
    ), candidate_gaps AS (
        SELECT sequence_id, created_at,
               LAG(created_at) OVER (ORDER BY created_at, sequence_id) AS previous_start
        FROM qualifying_starts
    ), grouped_starts AS (
        SELECT sequence_id, created_at,
               SUM(CASE WHEN previous_start IS NULL
                              OR created_at > previous_start + INTERVAL '1 hour'
                        THEN 1 ELSE 0 END)
                   OVER (ORDER BY created_at, sequence_id) AS incident_id
        FROM candidate_gaps
    ), representatives AS (
        SELECT DISTINCT ON (incident_id) incident_id, sequence_id
        FROM grouped_starts
        ORDER BY incident_id, created_at, sequence_id
    )
"""


def upgrade():
    op.create_index(
        "ix_hr_undo_actor_action_id",
        "hr_undo_actions",
        ["actor_user_id", "action_id"],
    )
    op.add_column(
        "suspicious_activity_flags",
        sa.Column("superseded_by_flag_id", sa.Integer(), nullable=True),
    )
    op.create_foreign_key(
        "fk_suspicious_flags_superseded_by",
        "suspicious_activity_flags",
        "suspicious_activity_flags",
        ["superseded_by_flag_id"],
        ["flag_id"],
    )
    op.create_check_constraint(
        "chk_suspicious_flags_not_self_superseded",
        "suspicious_activity_flags",
        "superseded_by_flag_id IS NULL OR superseded_by_flag_id <> flag_id",
    )
    op.create_index(
        "idx_suspicious_flags_superseded_by",
        "suspicious_activity_flags",
        ["superseded_by_flag_id"],
    )

    # Keep every original flag and review row. Link duplicate rows to the
    # earliest flag in their incident and carry any completed review forward.
    op.execute("CREATE TEMP TABLE argus_deactivation_flag_groups ON COMMIT DROP AS " + _DEACTIVATION_CTES + """
        SELECT grouped.incident_id,
               duplicate.flag_id AS flag_id,
               root.flag_id AS root_flag_id,
               duplicate.reviewed_by_user_id,
               duplicate.reviewed_at
        FROM grouped_starts AS grouped
        JOIN public.suspicious_activity_flags AS duplicate
          ON duplicate.audit_log_sequence_id = grouped.sequence_id
         AND duplicate.flag_reason = 'mass_employee_deactivations'
        JOIN representatives
          ON representatives.incident_id = grouped.incident_id
        JOIN public.suspicious_activity_flags AS root
          ON root.audit_log_sequence_id = representatives.sequence_id
         AND root.flag_reason = 'mass_employee_deactivations'
    """)
    op.execute("""
        UPDATE public.suspicious_activity_flags AS duplicate
        SET superseded_by_flag_id = grouped.root_flag_id
        FROM argus_deactivation_flag_groups AS grouped
        WHERE duplicate.flag_id = grouped.flag_id
          AND duplicate.flag_id <> grouped.root_flag_id
    """)
    op.execute("""
        WITH review_state AS (
            SELECT DISTINCT ON (incident_id)
                   incident_id, reviewed_by_user_id, reviewed_at, root_flag_id
            FROM argus_deactivation_flag_groups
            WHERE reviewed_at IS NOT NULL
            ORDER BY incident_id, reviewed_at DESC, flag_id DESC
        )
        UPDATE public.suspicious_activity_flags AS root
        SET reviewed_by_user_id = review_state.reviewed_by_user_id,
            reviewed_at = review_state.reviewed_at
        FROM review_state
        WHERE root.flag_id = review_state.root_flag_id
    """)

    op.execute("""
        CREATE OR REPLACE PROCEDURE public.refresh_suspicious_activity_flags()
        LANGUAGE plpgsql
        SECURITY DEFINER
        SET search_path = pg_catalog, public, pg_temp
        AS $$
        BEGIN
            WITH salary_changes AS (
                SELECT sequence_id,
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
            SELECT salary_changes.sequence_id, 'salary_change_exceeds_30_percent'
            FROM salary_changes
            WHERE salary_changes.prev_salary IS NOT NULL
              AND salary_changes.prev_salary > 0
              AND ABS(salary_changes.current_salary - salary_changes.prev_salary)
                    / salary_changes.prev_salary > 0.30
              AND NOT EXISTS (
                  SELECT 1 FROM public.suspicious_activity_flags flag
                  WHERE flag.audit_log_sequence_id = salary_changes.sequence_id
              );

            INSERT INTO public.suspicious_activity_flags (audit_log_sequence_id, flag_reason)
            SELECT audit.sequence_id, 'data_deletion'
            FROM public.audit_log audit
            WHERE audit.action = 'DELETE'
              AND NOT EXISTS (
                  SELECT 1 FROM public.suspicious_activity_flags flag
                  WHERE flag.audit_log_sequence_id = audit.sequence_id
              );

            WITH deactivation_events AS (
                SELECT sequence_id, created_at
                FROM public.audit_log
                WHERE table_name = 'employees'
                  AND action = 'UPDATE'
                  AND old_value->>'is_active' = 'true'
                  AND new_value->>'is_active' = 'false'
            ), qualifying_starts AS (
                SELECT sequence_id, created_at
                FROM (
                    SELECT sequence_id, created_at,
                           COUNT(*) OVER (
                               ORDER BY created_at
                               RANGE BETWEEN CURRENT ROW AND INTERVAL '1 hour' FOLLOWING
                           ) AS events_in_next_hour
                    FROM deactivation_events
                ) counted
                WHERE events_in_next_hour > 3
            ), candidate_gaps AS (
                SELECT sequence_id, created_at,
                       LAG(created_at) OVER (ORDER BY created_at, sequence_id) AS previous_start
                FROM qualifying_starts
            ), grouped_starts AS (
                SELECT sequence_id, created_at,
                       SUM(CASE WHEN previous_start IS NULL
                                      OR created_at > previous_start + INTERVAL '1 hour'
                                THEN 1 ELSE 0 END)
                           OVER (ORDER BY created_at, sequence_id) AS incident_id
                FROM candidate_gaps
            ), representatives AS (
                SELECT DISTINCT ON (incident_id) incident_id, sequence_id
                FROM grouped_starts
                ORDER BY incident_id, created_at, sequence_id
            )
            INSERT INTO public.suspicious_activity_flags (audit_log_sequence_id, flag_reason)
            SELECT representatives.sequence_id, 'mass_employee_deactivations'
            FROM representatives
            WHERE NOT EXISTS (
                SELECT 1 FROM public.suspicious_activity_flags flag
                WHERE flag.audit_log_sequence_id = representatives.sequence_id
            );
        END;
        $$
    """)


def downgrade():
    op.drop_index("idx_suspicious_flags_superseded_by", table_name="suspicious_activity_flags")
    op.drop_constraint("chk_suspicious_flags_not_self_superseded", "suspicious_activity_flags", type_="check")
    op.drop_constraint("fk_suspicious_flags_superseded_by", "suspicious_activity_flags", type_="foreignkey")
    op.drop_column("suspicious_activity_flags", "superseded_by_flag_id")
    op.drop_index("ix_hr_undo_actor_action_id", table_name="hr_undo_actions")
