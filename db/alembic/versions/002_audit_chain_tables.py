"""DB-002: Create Audit & Chain Tables

Revision ID: 002_audit_chain_tables
Revises: 001_core_entity_tables
Create Date: 2026-07-25 10:05:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = '002_audit_chain_tables'
down_revision: Union[str, None] = '001_core_entity_tables'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 6. Audit Log Table
    op.create_table(
        'audit_log',
        sa.Column('sequence_id', sa.BigInteger(), nullable=False),
        sa.Column('actor_user_id', sa.Integer(), nullable=False),
        sa.Column('employee_id', sa.Integer(), nullable=True),
        sa.Column('action', sa.String(length=20), nullable=False),
        sa.Column('table_name', sa.String(length=100), nullable=False),
        sa.Column('row_id', sa.Integer(), nullable=False),
        sa.Column('old_value', postgresql.JSONB(astext_type=sa.Text()).with_variant(sa.JSON(), 'sqlite'), nullable=True),
        sa.Column('new_value', postgresql.JSONB(astext_type=sa.Text()).with_variant(sa.JSON(), 'sqlite'), nullable=True),
        sa.Column('severity', sa.String(length=20), nullable=False),
        sa.Column('entry_hash', sa.String(length=64), nullable=False),
        sa.Column('previous_hash', sa.String(length=64), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.CheckConstraint("action IN ('INSERT', 'UPDATE', 'DELETE')", name='chk_audit_log_action'),
        sa.CheckConstraint("severity IN ('INFO', 'WARNING', 'CRITICAL')", name='chk_audit_log_severity'),
        sa.ForeignKeyConstraint(['actor_user_id'], ['users.user_id'], name='fk_audit_log_actor_user_id'),
        sa.ForeignKeyConstraint(['employee_id'], ['employees.employee_id'], name='fk_audit_log_employee_id'),
        sa.PrimaryKeyConstraint('sequence_id')
    )

    # Indices on audit_log
    op.create_index('idx_audit_log_seq_time', 'audit_log', ['sequence_id', 'created_at'])
    op.create_index('idx_audit_log_employee_time', 'audit_log', ['employee_id', 'created_at'])

    # 7. Suspicious Activity Flags Table
    op.create_table(
        'suspicious_activity_flags',
        sa.Column('flag_id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('audit_log_sequence_id', sa.BigInteger(), nullable=False),
        sa.Column('reviewed_by_user_id', sa.Integer(), nullable=True),
        sa.Column('reviewed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('flag_reason', sa.String(length=255), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.ForeignKeyConstraint(['audit_log_sequence_id'], ['audit_log.sequence_id'], name='fk_suspicious_flags_audit_log_sequence_id'),
        sa.ForeignKeyConstraint(['reviewed_by_user_id'], ['users.user_id'], name='fk_suspicious_flags_reviewed_by_user_id'),
        sa.PrimaryKeyConstraint('flag_id')
    )

    # 8. Chain State Table (Singleton)
    op.create_table(
        'chain_state',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('tail_hash', sa.String(length=64), nullable=False),
        sa.Column('tail_sequence_id', sa.BigInteger(), nullable=False),
        sa.Column('last_checkpoint_sequence_id', sa.BigInteger(), nullable=False),
        sa.CheckConstraint('id = 1', name='chk_chain_state_singleton'),
        sa.PrimaryKeyConstraint('id')
    )

    # 9. Chain Checkpoints Table
    op.create_table(
        'chain_checkpoints',
        sa.Column('checkpoint_id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('sequence_id', sa.BigInteger(), nullable=False),
        sa.Column('checkpoint_hash', sa.String(length=64), nullable=False),
        sa.Column('signature', sa.LargeBinary(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.ForeignKeyConstraint(['sequence_id'], ['audit_log.sequence_id'], name='fk_chain_checkpoints_sequence_id'),
        sa.PrimaryKeyConstraint('checkpoint_id')
    )

    # 10. Backups Table
    op.create_table(
        'backups',
        sa.Column('backup_id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('chain_checkpoint_id', sa.Integer(), nullable=True),
        sa.Column('backup_hash', sa.String(length=64), nullable=False),
        sa.Column('file_reference', sa.String(length=255), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.ForeignKeyConstraint(['chain_checkpoint_id'], ['chain_checkpoints.checkpoint_id'], name='fk_backups_chain_checkpoint_id'),
        sa.PrimaryKeyConstraint('backup_id')
    )


def downgrade() -> None:
    # Drop in reverse dependency order
    op.drop_table('backups')
    op.drop_table('chain_checkpoints')
    op.drop_table('chain_state')
    op.drop_table('suspicious_activity_flags')
    op.drop_index('idx_audit_log_employee_time', table_name='audit_log')
    op.drop_index('idx_audit_log_seq_time', table_name='audit_log')
    op.drop_table('audit_log')
