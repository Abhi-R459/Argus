"""DB-007, DB-009, DB-010: Hash-Chaining AFTER Trigger on employees (with severity + masking helpers)

Revision ID: 005_trigger_employees
Revises: 004_views
Create Date: 2026-07-31

Deploys:
  - mask_employee_payload() helper function (DB-010)
  - assign_severity()        helper function (DB-009)
  - trg_employees_hash_chain_fn() trigger function
  - trg_employees_hash_chain      trigger on employees
"""
from typing import Sequence, Union
from pathlib import Path

from alembic import op


# revision identifiers, used by Alembic.
revision: str = '005_trigger_employees'
down_revision: Union[str, None] = '004_views'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Path to the SQL file relative to this migration's parent package root
_SQL_FILE = Path(__file__).parent.parent.parent / 'triggers' / 'audit_employees.sql'


def upgrade() -> None:
    """Apply hash-chain trigger and helper functions on employees."""
    sql = _SQL_FILE.read_text(encoding='utf-8')
    op.execute(sql)


def downgrade() -> None:
    """Remove the trigger and helper functions."""
    op.execute("DROP TRIGGER IF EXISTS trg_employees_hash_chain ON employees;")
    op.execute("DROP FUNCTION IF EXISTS trg_employees_hash_chain_fn();")
    op.execute("DROP FUNCTION IF EXISTS assign_severity(TEXT, TEXT);")
    op.execute("DROP FUNCTION IF EXISTS mask_employee_payload(JSONB);")
