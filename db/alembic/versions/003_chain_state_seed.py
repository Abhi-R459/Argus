"""DB-003: Seed Chain State Singleton Row

Revision ID: 003_chain_state_seed
Revises: 002_audit_chain_tables
Create Date: 2026-07-25 10:10:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '003_chain_state_seed'
down_revision: Union[str, None] = '002_audit_chain_tables'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Seed the singleton row for chain_state (id=1, tail_hash=64 zeroes, sequence=0, last_checkpoint=0)
    initial_hash = '0' * 64
    op.execute(
        f"INSERT INTO chain_state (id, tail_hash, tail_sequence_id, last_checkpoint_sequence_id) "
        f"VALUES (1, '{initial_hash}', 0, 0)"
    )


def downgrade() -> None:
    op.execute("DELETE FROM chain_state WHERE id = 1")
