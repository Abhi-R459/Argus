"""Add provider links without rewriting legacy user IDs or audit references."""

from alembic import op
import sqlalchemy as sa


revision = "034_clerk_identity_links"
down_revision = "033_schedule_auditor_id"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "auth_identities",
        sa.Column("provider", sa.String(32), primary_key=True),
        sa.Column("subject", sa.String(255), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.user_id"), nullable=False),
        sa.UniqueConstraint("provider", "user_id", name="uq_auth_identity_provider_user"),
    )
    op.execute("REVOKE ALL ON public.auth_identities FROM PUBLIC")
    op.execute("ALTER TABLE public.auth_identities ENABLE ROW LEVEL SECURITY")
    op.execute("""
        DO $$ BEGIN
          IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'hr_admin') THEN
            GRANT SELECT, INSERT ON public.auth_identities TO hr_admin;
            CREATE POLICY auth_identity_hr ON public.auth_identities
              FOR ALL TO hr_admin USING (true) WITH CHECK (true);
          END IF;
        END $$;
    """)


def downgrade():
    op.drop_table("auth_identities")
