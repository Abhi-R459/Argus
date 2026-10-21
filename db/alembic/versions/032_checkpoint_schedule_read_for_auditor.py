"""Let auditors read the non-sensitive checkpoint interval setting."""

from alembic import op


revision = "032_checkpoint_schedule_read_for_auditor"
down_revision = "031_checkpoint_schedule_settings"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""
        DO $$ BEGIN
            IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'compliance_auditor') THEN
                GRANT SELECT (enabled, interval_events)
                ON public.checkpoint_schedule_settings TO compliance_auditor;
            END IF;
        END $$;
    """)
    op.execute("""
        CREATE POLICY checkpoint_schedule_auditor_read
        ON public.checkpoint_schedule_settings
        FOR SELECT TO compliance_auditor
        USING (true)
    """)


def downgrade():
    op.execute("""
        DROP POLICY IF EXISTS checkpoint_schedule_auditor_read
        ON public.checkpoint_schedule_settings
    """)
    op.execute("""
        REVOKE SELECT (enabled, interval_events)
        ON public.checkpoint_schedule_settings FROM compliance_auditor
    """)
