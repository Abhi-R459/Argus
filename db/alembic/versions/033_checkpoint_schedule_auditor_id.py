"""Allow auditors to filter the singleton schedule row."""

from alembic import op


revision = "033_schedule_auditor_id"
down_revision = "032_checkpoint_schedule_auditor"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""
        DO $$ BEGIN
            IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'compliance_auditor') THEN
                GRANT SELECT (id)
                ON public.checkpoint_schedule_settings TO compliance_auditor;
            END IF;
        END $$;
    """)


def downgrade():
    op.execute("""
        REVOKE SELECT (id)
        ON public.checkpoint_schedule_settings FROM compliance_auditor
    """)
