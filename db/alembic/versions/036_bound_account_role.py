"""Bind each Clerk account to one immutable workspace role."""

from alembic import op
import sqlalchemy as sa

revision = "036_bound_account_role"
down_revision = "035_hr_undo_actions"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("users", sa.Column("account_role", sa.String(50), nullable=True))
    op.create_check_constraint(
        "users_account_role_check", "users",
        "account_role IS NULL OR account_role IN ('hr_admin', 'compliance_auditor')",
    )
    op.execute("""
        CREATE FUNCTION public.argus_lock_account_role() RETURNS trigger
        LANGUAGE plpgsql SET search_path = pg_catalog, pg_temp AS $$
        BEGIN
          IF OLD.account_role IS NOT NULL AND
             (NEW.account_role IS DISTINCT FROM OLD.account_role OR NEW.role IS DISTINCT FROM OLD.role) THEN
            RAISE EXCEPTION 'Account role is immutable' USING ERRCODE = '23514';
          END IF;
          IF NEW.account_role IS NOT NULL AND NEW.role IS DISTINCT FROM NEW.account_role THEN
            RAISE EXCEPTION 'Account role and database role must match' USING ERRCODE = '23514';
          END IF;
          RETURN NEW;
        END $$;
        REVOKE ALL ON FUNCTION public.argus_lock_account_role() FROM PUBLIC;
        CREATE TRIGGER lock_account_role BEFORE UPDATE ON public.users
          FOR EACH ROW EXECUTE FUNCTION public.argus_lock_account_role();
    """)
    # Existing accounts keep their historical role only for release rollback.
    # account_role remains NULL until the user makes a deliberate choice.


def downgrade():
    op.execute("DROP TRIGGER lock_account_role ON public.users")
    op.execute("DROP FUNCTION public.argus_lock_account_role()")
    op.drop_constraint("users_account_role_check", "users", type_="check")
    op.drop_column("users", "account_role")
