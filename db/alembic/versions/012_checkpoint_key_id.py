"""HARDEN-008: Checkpoint key_id metadata for seamless key rotation.

Revision ID: 012_checkpoint_key_id
Revises: 011_audit_log_hardening
Create Date: 2026-09-13 11:15:00.000000

Adds key_id column to chain_checkpoints table to record which cryptographic
key was active when the checkpoint was created, allowing seamless key
rotation without invalidating historical checkpoints.
"""

from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "012_checkpoint_key_id"
down_revision: Union[str, None] = "011_audit_log_hardening"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add key_id metadata column to chain_checkpoints."""
    op.add_column(
        "chain_checkpoints",
        sa.Column(
            "key_id",
            sa.String(length=128),
            nullable=True,
            server_default="local:ed25519:v1",
        ),
    )


def downgrade() -> None:
    """Drop key_id column from chain_checkpoints."""
    op.drop_column("chain_checkpoints", "key_id")
