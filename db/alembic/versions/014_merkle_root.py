"""NOVEL-009: Merkle Root and Leaf Count for chain_checkpoints.

Revision ID: 014_merkle_root
Revises: 013_tunable_pbkdf2_blind_index
Create Date: 2026-09-25 14:10:00.000000

Adds merkle_root and merkle_leaf_count columns to chain_checkpoints table
to enable RFC 6962-compliant per-checkpoint Merkle Hash Trees for logarithmic
audit proofs (O(log K)) and selective disclosure capsules (.arguscap).
"""

from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "014_merkle_root"
down_revision: Union[str, None] = "013_tunable_pbkdf2_blind_index"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add merkle_root and merkle_leaf_count columns to chain_checkpoints."""
    op.add_column(
        "chain_checkpoints",
        sa.Column(
            "merkle_root",
            sa.Text(),
            nullable=True,
        ),
    )
    op.add_column(
        "chain_checkpoints",
        sa.Column(
            "merkle_leaf_count",
            sa.Integer(),
            nullable=True,
        ),
    )


def downgrade() -> None:
    """Drop merkle_leaf_count and merkle_root columns from chain_checkpoints."""
    op.drop_column("chain_checkpoints", "merkle_leaf_count")
    op.drop_column("chain_checkpoints", "merkle_root")
