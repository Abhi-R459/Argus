"""HARDEN: Pin SECURITY DEFINER audit trigger search paths.

Revision ID: 016_secure_trigger_search_path
Revises: 015_sec_audit_events
"""

from typing import Sequence, Union

from alembic import op


revision: str = "016_secure_trigger_search_path"
down_revision: Union[str, None] = "015_sec_audit_events"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Put trusted schemas first and the caller's temporary schema last."""
    # Supabase installs pgcrypto into `extensions`, while a stock PostgreSQL
    # installation commonly installs it into `public`. Keep both trusted
    # schemas on the pinned path so hash functions resolve in either layout.
    op.execute("ALTER FUNCTION public.trg_employees_hash_chain_fn() SET search_path TO pg_catalog, public, extensions, pg_temp")
    op.execute("ALTER FUNCTION public.trg_salary_history_hash_chain_fn() SET search_path TO pg_catalog, public, extensions, pg_temp")


def downgrade() -> None:
    """Restore PostgreSQL's default function search path."""
    op.execute("ALTER FUNCTION public.trg_salary_history_hash_chain_fn() RESET search_path")
    op.execute("ALTER FUNCTION public.trg_employees_hash_chain_fn() RESET search_path")
