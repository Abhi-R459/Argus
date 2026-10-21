"""Persist the HR controlled automatic checkpoint schedule."""

from alembic import op
import sqlalchemy as sa


revision = "031_checkpoint_schedule_settings"
down_revision = "030_definer_schema_usage"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "checkpoint_schedule_settings",
        sa.Column("id", sa.SmallInteger(), primary_key=True),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("interval_events", sa.Integer(), nullable=False, server_default="50"),
        sa.Column("updated_by", sa.Integer(),
                  sa.ForeignKey("users.user_id", ondelete="SET NULL"), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.func.now()),
        sa.CheckConstraint("id = 1", name="ck_checkpoint_schedule_singleton"),
        sa.CheckConstraint("interval_events BETWEEN 1 AND 10000",
                           name="ck_checkpoint_schedule_interval"),
    )
    op.execute("""
        INSERT INTO public.checkpoint_schedule_settings (id, enabled, interval_events)
        VALUES (1, TRUE, 50)
    """)
    op.execute("""
        DO $$ BEGIN
            IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'hr_admin') THEN
                GRANT SELECT, UPDATE ON public.checkpoint_schedule_settings TO hr_admin;
            END IF;
        END $$;
    """)
    op.execute("ALTER TABLE public.checkpoint_schedule_settings ENABLE ROW LEVEL SECURITY")
    op.execute("""
        CREATE POLICY checkpoint_schedule_hr_access
        ON public.checkpoint_schedule_settings
        TO hr_admin
        USING (true)
        WITH CHECK (true)
    """)


def downgrade():
    op.drop_table("checkpoint_schedule_settings")
