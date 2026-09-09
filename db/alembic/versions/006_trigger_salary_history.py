"""DB-008: Hash-Chaining AFTER Trigger on salary_history

Revision ID: 006_trigger_salary_history
Revises: 005_trigger_employees
Create Date: 2026-07-31

Deploys:
  - trg_salary_history_hash_chain_fn() trigger function
  - trg_salary_history_hash_chain      trigger on salary_history
"""
from typing import Sequence, Union
from pathlib import Path

from alembic import op


# revision identifiers, used by Alembic.
revision: str = '006_trigger_salary_history'
down_revision: Union[str, None] = '005_trigger_employees'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_SQL_FILE = Path(__file__).parent.parent.parent / 'triggers' / 'audit_salary_history.sql'


def upgrade() -> None:
    """Apply hash-chain trigger on salary_history."""
    sql = _SQL_FILE.read_text(encoding='utf-8')
    op.execute(sql)


def downgrade() -> None:
    """Remove salary_history trigger."""
    op.execute("DROP TRIGGER IF EXISTS trg_salary_history_hash_chain ON salary_history;")
    op.execute("DROP FUNCTION IF EXISTS trg_salary_history_hash_chain_fn();")
