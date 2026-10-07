"""Allow HR admins to create signed checkpoints through the authorized API.

Revision ID: 023_hr_checkpoint_creation
Revises: 022_search_path_fk_indexes
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op


revision: str = "023_hr_checkpoint_creation"
down_revision: Union[str, None] = "022_search_path_fk_indexes"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Grant only append permissions required by the authenticated checkpoint API."""
    if op.get_bind().dialect.name != "postgresql":
        return
    op.execute("""
        DO $$ BEGIN
            IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'hr_admin') THEN
                GRANT INSERT ON chain_checkpoints TO hr_admin;
                GRANT USAGE, SELECT ON SEQUENCE chain_checkpoints_checkpoint_id_seq TO hr_admin;
                GRANT INSERT ON security_audit_events TO hr_admin;
                GRANT USAGE, SELECT ON SEQUENCE security_audit_events_event_id_seq TO hr_admin;
                REVOKE UPDATE, DELETE, TRUNCATE ON chain_checkpoints FROM hr_admin;
                REVOKE UPDATE, DELETE, TRUNCATE ON security_audit_events FROM hr_admin;
            END IF;
        END $$;
    """)


def downgrade() -> None:
    """Remove checkpoint append access from the HR runtime role."""
    if op.get_bind().dialect.name != "postgresql":
        return
    op.execute("""
        DO $$ BEGIN
            IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'hr_admin') THEN
                REVOKE INSERT ON chain_checkpoints FROM hr_admin;
                REVOKE USAGE, SELECT ON SEQUENCE chain_checkpoints_checkpoint_id_seq FROM hr_admin;
                REVOKE INSERT ON security_audit_events FROM hr_admin;
                REVOKE USAGE, SELECT ON SEQUENCE security_audit_events_event_id_seq FROM hr_admin;
            END IF;
        END $$;
    """)
