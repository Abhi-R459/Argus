"""Make checkpoint idempotency enforceable by PostgreSQL.

Revision ID: 020_unique_checkpoint_sequence
Revises: 019_signed_actor_context
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "020_unique_checkpoint_sequence"
down_revision: Union[str, None] = "019_signed_actor_context"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    duplicates = op.get_bind().execute(sa.text("""
        SELECT sequence_id, count(*) AS row_count
        FROM chain_checkpoints
        GROUP BY sequence_id
        HAVING count(*) > 1
        ORDER BY sequence_id
        LIMIT 1
    """)).first()
    if duplicates:
        raise RuntimeError(
            "Cannot add checkpoint idempotency constraint: duplicate rows exist "
            f"for audit sequence {duplicates.sequence_id} ({duplicates.row_count} checkpoints). "
            "Review and reconcile these rows before retrying the migration."
        )
    op.create_unique_constraint(
        "uq_chain_checkpoints_sequence_id",
        "chain_checkpoints",
        ["sequence_id"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "uq_chain_checkpoints_sequence_id",
        "chain_checkpoints",
        type_="unique",
    )
