"""Store encrypted preimages for forward-only HR undo."""

from alembic import op
import sqlalchemy as sa


revision = "035_hr_undo_actions"
down_revision = "034_clerk_identity_links"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "hr_undo_actions",
        sa.Column("action_id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("employee_id", sa.Integer(), sa.ForeignKey("employees.employee_id"), nullable=False),
        sa.Column("action_type", sa.String(32), nullable=False),
        sa.Column("actor_user_id", sa.Integer(), sa.ForeignKey("users.user_id"), nullable=False),
        sa.Column("before_ciphertext", sa.LargeBinary()),
        sa.Column("after_hash", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("undone_at", sa.DateTime(timezone=True)),
        sa.Column("undone_by_user_id", sa.Integer(), sa.ForeignKey("users.user_id")),
    )
    op.create_index("ix_hr_undo_employee_created", "hr_undo_actions", ["employee_id", "created_at"])
    op.execute("REVOKE ALL ON public.hr_undo_actions FROM PUBLIC")
    op.execute("ALTER TABLE public.hr_undo_actions ENABLE ROW LEVEL SECURITY")
    op.execute("""
        DO $$ BEGIN
          IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'hr_admin') THEN
            GRANT SELECT, INSERT, UPDATE ON public.hr_undo_actions TO hr_admin;
            GRANT USAGE, SELECT ON SEQUENCE public.hr_undo_actions_action_id_seq TO hr_admin;
            CREATE POLICY hr_undo_hr ON public.hr_undo_actions
              FOR ALL TO hr_admin USING (true) WITH CHECK (true);
          END IF;
        END $$;
    """)


def downgrade():
    op.drop_index("ix_hr_undo_employee_created", table_name="hr_undo_actions")
    op.drop_table("hr_undo_actions")
