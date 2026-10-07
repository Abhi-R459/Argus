"""Remove Supabase Data API defaults from Argus's public schema.

Revision ID: 021_supabase_lockdown
Revises: 020_unique_checkpoint_sequence
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op


revision: str = "021_supabase_lockdown"
down_revision: Union[str, None] = "020_unique_checkpoint_sequence"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Revoke Supabase API and PUBLIC defaults while preserving app roles."""
    if op.get_bind().dialect.name != "postgresql":
        return

    op.execute("REVOKE USAGE, CREATE ON SCHEMA public FROM PUBLIC")
    op.execute("REVOKE ALL PRIVILEGES ON ALL TABLES IN SCHEMA public FROM PUBLIC")
    op.execute("REVOKE ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public FROM PUBLIC")
    # A managed PostgreSQL migration login may not own routines that an
    # earlier migration deliberately transferred to a dedicated NOLOGIN
    # owner. That owner already revokes PUBLIC on its security-definer
    # routines; revoke the default execute grant from routines owned by this
    # migration principal only.
    op.execute("""
        DO $$
        DECLARE
            v_routine RECORD;
        BEGIN
            FOR v_routine IN
                SELECT n.nspname, p.proname,
                       pg_get_function_identity_arguments(p.oid) AS identity_args,
                       p.prokind
                FROM pg_proc AS p
                JOIN pg_namespace AS n ON n.oid = p.pronamespace
                WHERE n.nspname = 'public'
                  AND p.proowner = (SELECT oid FROM pg_roles WHERE rolname = current_user)
            LOOP
                EXECUTE format(
                    'REVOKE EXECUTE ON %s %I.%I(%s) FROM PUBLIC',
                    CASE WHEN v_routine.prokind = 'p' THEN 'PROCEDURE' ELSE 'FUNCTION' END,
                    v_routine.nspname, v_routine.proname, v_routine.identity_args
                );
            END LOOP;
        END $$;
    """)
    op.execute("""
        DO $$
        DECLARE
            v_owner NAME := current_user;
            v_role NAME;
            v_routine RECORD;
        BEGIN
            FOR v_role IN
                SELECT rolname FROM pg_roles
                WHERE rolname IN ('anon', 'authenticated', 'service_role')
            LOOP
                EXECUTE format('REVOKE USAGE, CREATE ON SCHEMA public FROM %I', v_role);
                EXECUTE format('REVOKE ALL PRIVILEGES ON ALL TABLES IN SCHEMA public FROM %I', v_role);
                EXECUTE format('REVOKE ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public FROM %I', v_role);
                FOR v_routine IN
                    SELECT n.nspname, p.proname,
                           pg_get_function_identity_arguments(p.oid) AS identity_args,
                           p.prokind
                    FROM pg_proc AS p
                    JOIN pg_namespace AS n ON n.oid = p.pronamespace
                    WHERE n.nspname = 'public'
                      AND p.proowner = (SELECT oid FROM pg_roles WHERE rolname = v_owner)
                LOOP
                    EXECUTE format(
                        'REVOKE EXECUTE ON %s %I.%I(%s) FROM %I',
                        CASE WHEN v_routine.prokind = 'p' THEN 'PROCEDURE' ELSE 'FUNCTION' END,
                        v_routine.nspname, v_routine.proname,
                        v_routine.identity_args, v_role
                    );
                END LOOP;
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
            EXECUTE format(
                'ALTER DEFAULT PRIVILEGES FOR ROLE %I REVOKE EXECUTE ON ROUTINES FROM PUBLIC',
                v_owner
            );
        END $$;
    """)

    # These are the only public-schema routines directly invoked by the API.
    # Grant only to the Auditor identity that owns those workflows.
    op.execute("""
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'compliance_auditor') THEN
                GRANT EXECUTE ON FUNCTION public.reconstruct_employee_state(INTEGER, TIMESTAMPTZ)
                    TO compliance_auditor;
                GRANT EXECUTE ON PROCEDURE public.refresh_suspicious_activity_flags()
                    TO compliance_auditor;
            END IF;
        END $$;
    """)


def downgrade() -> None:
    """Keep public API access closed; restoring broad defaults is unsafe."""
    raise RuntimeError(
        "Public schema API access is intentionally restricted. Apply a reviewed forward migration to change the privilege boundary."
    )
