"""Pin routine lookup paths and index audited foreign-key columns.

Revision ID: 022_search_path_fk_indexes
Revises: 021_supabase_lockdown
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op


revision: str = "022_search_path_fk_indexes"
down_revision: Union[str, None] = "021_supabase_lockdown"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_ROUTINES = (
    ("FUNCTION", "assign_severity", "(text, text)", "pg_catalog, public, pg_temp"),
    (
        "FUNCTION",
        "trg_employees_national_id_immutable_fn",
        "()",
        "pg_catalog, public, pg_temp",
    ),
    (
        "FUNCTION",
        "trg_salary_history_decrease_check_fn",
        "()",
        "pg_catalog, public, pg_temp",
    ),
    (
        "FUNCTION",
        "mask_employee_payload",
        "(jsonb)",
        "pg_catalog, public, extensions, pg_temp",
    ),
    (
        "FUNCTION",
        "trg_salary_history_self_block_fn",
        "()",
        "pg_catalog, public, pg_temp",
    ),
    (
        "FUNCTION",
        "reconstruct_employee_state",
        "(integer, timestamp with time zone)",
        "pg_catalog, public, pg_temp",
    ),
    (
        "FUNCTION",
        "compute_blind_index",
        "(text, text, integer)",
        "pg_catalog, public, extensions, pg_temp",
    ),
    (
        "PROCEDURE",
        "refresh_suspicious_activity_flags",
        "()",
        "pg_catalog, public, pg_temp",
    ),
)

_INDEXES = (
    (
        "argus_private.actor_context_nonces",
        "actor_user_id",
        "ix_actor_context_nonces_actor_user_id",
    ),
    ("public.audit_log", "actor_user_id", "ix_audit_log_actor_user_id"),
    ("public.backups", "chain_checkpoint_id", "ix_backups_chain_checkpoint_id"),
    ("public.employees", "role_id", "ix_employees_role_id"),
    ("public.roles", "department_id", "ix_roles_department_id"),
    (
        "public.suspicious_activity_flags",
        "audit_log_sequence_id",
        "ix_suspicious_flags_audit_log_sequence_id",
    ),
    (
        "public.suspicious_activity_flags",
        "reviewed_by_user_id",
        "ix_suspicious_flags_reviewed_by_user_id",
    ),
    (
        "public.suspicious_activity_reviews",
        "reviewer_user_id",
        "ix_suspicious_activity_reviews_reviewer_user_id",
    ),
)


def upgrade() -> None:
    """Pin all linter-reported routines and add online FK support indexes."""
    if op.get_bind().dialect.name != "postgresql":
        return

    for routine_type, name, signature, search_path in _ROUTINES:
        op.execute(
            f"ALTER {routine_type} public.{name}{signature} "
            f"SET search_path TO {search_path}"
        )

    # Concurrent index builds avoid blocking normal reads and writes. Each is
    # committed independently; IF NOT EXISTS makes retry after a partial run safe.
    for table, column, index in _INDEXES:
        with op.get_context().autocommit_block():
            statement = (
                f"CREATE INDEX CONCURRENTLY IF NOT EXISTS {index} "
                f"ON {table} ({column})"
            )
            if table.startswith("argus_private."):
                # The private nonce table is intentionally owned by a NOLOGIN
                # role. Supabase's migration principal can assume that role
                # temporarily, but is not a superuser and cannot index the
                # table directly.
                op.execute("GRANT argus_audit_owner TO CURRENT_USER")
                op.execute("SET ROLE argus_audit_owner")
                try:
                    op.execute(statement)
                finally:
                    op.execute("RESET ROLE")
                    op.execute("REVOKE argus_audit_owner FROM CURRENT_USER")
            else:
                op.execute(statement)


def downgrade() -> None:
    """Keep hardened search paths and performance indexes in place."""
    raise RuntimeError(
        "Pinned routine search paths and foreign-key indexes are forward-only production hardening."
    )
