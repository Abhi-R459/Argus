"""DB-012, DB-013, DB-014: Business Rule BEFORE Triggers

Revision ID: 007_trigger_business_rules
Revises: 006_trigger_salary_history
Create Date: 2026-07-31

Deploys:
  - trg_employees_national_id_immutable_fn()  + trigger  (DB-013)
  - trg_salary_history_decrease_check_fn()    + trigger  (DB-012)
  - trg_salary_history_self_block_fn()        + trigger  (DB-014)
"""
from typing import Sequence, Union
from pathlib import Path

from alembic import op


# revision identifiers, used by Alembic.
revision: str = '007_trigger_business_rules'
down_revision: Union[str, None] = '006_trigger_salary_history'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_SQL_FILE = Path(__file__).parent.parent.parent / 'triggers' / 'business_rules.sql'


def upgrade() -> None:
    """Apply all three business-rule triggers."""
    sql = _SQL_FILE.read_text(encoding='utf-8')
    op.execute(sql)


def downgrade() -> None:
    """Remove business-rule triggers and functions."""
    op.execute("DROP TRIGGER IF EXISTS trg_salary_history_self_block ON salary_history;")
    op.execute("DROP FUNCTION IF EXISTS trg_salary_history_self_block_fn();")
    op.execute("DROP TRIGGER IF EXISTS trg_salary_history_decrease_check ON salary_history;")
    op.execute("DROP FUNCTION IF EXISTS trg_salary_history_decrease_check_fn();")
    op.execute("DROP TRIGGER IF EXISTS trg_employees_national_id_immutable ON employees;")
    op.execute("DROP FUNCTION IF EXISTS trg_employees_national_id_immutable_fn();")
