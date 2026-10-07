"""PROD-HARDEN-001: Persist privacy-preserving auditor security events.

Revision ID: 015_sec_audit_events
Revises: 014_merkle_root
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "015_sec_audit_events"
down_revision: Union[str, None] = "014_merkle_root"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "security_audit_events",
        sa.Column("event_id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("event_type", sa.String(length=64), nullable=False),
        sa.Column("actor_user_id", sa.Integer(), nullable=False),
        sa.Column("actor_email", sa.String(length=255), nullable=False),
        sa.Column("blind_index", sa.String(length=64), nullable=True),
        sa.Column("employee_id", sa.Integer(), nullable=True),
        sa.Column("sequence_id", sa.BigInteger(), nullable=True),
        sa.Column("matches_found", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("client_ip", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.PrimaryKeyConstraint("event_id"),
        sa.CheckConstraint("matches_found >= 0", name="chk_security_audit_events_matches"),
    )
    op.create_index("idx_security_audit_events_created", "security_audit_events", ["created_at", "event_id"])
    op.create_index("idx_security_audit_events_actor", "security_audit_events", ["actor_user_id", "created_at"])
    op.create_table(
        "suspicious_activity_reviews",
        sa.Column("review_id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("flag_id", sa.Integer(), nullable=False),
        sa.Column("reviewer_user_id", sa.Integer(), nullable=False),
        sa.Column("action", sa.String(length=16), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.ForeignKeyConstraint(["flag_id"], ["suspicious_activity_flags.flag_id"], name="fk_suspicious_activity_reviews_flag"),
        sa.ForeignKeyConstraint(["reviewer_user_id"], ["users.user_id"], name="fk_suspicious_activity_reviews_reviewer"),
        sa.CheckConstraint("action IN ('reviewed', 'reopened')", name="chk_suspicious_activity_reviews_action"),
        sa.PrimaryKeyConstraint("review_id"),
    )
    op.create_index("idx_suspicious_activity_reviews_flag", "suspicious_activity_reviews", ["flag_id", "created_at"])
    op.execute("""
        DO $$ BEGIN
            IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'compliance_auditor') THEN
                GRANT SELECT, INSERT ON security_audit_events TO compliance_auditor;
                REVOKE UPDATE, DELETE, TRUNCATE ON security_audit_events FROM compliance_auditor;
                GRANT USAGE, SELECT ON SEQUENCE security_audit_events_event_id_seq TO compliance_auditor;
                GRANT SELECT, INSERT ON suspicious_activity_reviews TO compliance_auditor;
                REVOKE UPDATE, DELETE, TRUNCATE ON suspicious_activity_reviews FROM compliance_auditor;
                GRANT USAGE, SELECT ON SEQUENCE suspicious_activity_reviews_review_id_seq TO compliance_auditor;
            END IF;
        END $$;
    """)


def downgrade() -> None:
    op.drop_index("idx_suspicious_activity_reviews_flag", table_name="suspicious_activity_reviews")
    op.drop_table("suspicious_activity_reviews")
    op.drop_index("idx_security_audit_events_actor", table_name="security_audit_events")
    op.drop_index("idx_security_audit_events_created", table_name="security_audit_events")
    op.drop_table("security_audit_events")
