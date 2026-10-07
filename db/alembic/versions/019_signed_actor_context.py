"""Require database-verified actor assertions for runtime HR writes.

Revision ID: 019_signed_actor_context
Revises: 018_encrypt_employee_pii
"""

from __future__ import annotations

import os
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

from db.crypto.actor_context import parse_context_secret, canonical_actor_payload


revision: str = "019_signed_actor_context"
down_revision: Union[str, None] = "018_encrypt_employee_pii"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    secret_hex = os.environ.get("AUDIT_CONTEXT_SECRET", "")
    key_id = os.environ.get("AUDIT_CONTEXT_KEY_ID", "v1")
    secret = parse_context_secret(secret_hex)
    # Reuse the protocol validator so the DB and Python signer accept the same key IDs.
    canonical_actor_payload(
        key_id=key_id,
        actor_user_id=1,
        actor_employee_id=0,
        db_role="hr_admin",
        nonce="00000000-0000-0000-0000-000000000000",
        issued_at=1,
        expires_at=2,
    )

    bind = op.get_bind()
    bind.execute(sa.text("CREATE EXTENSION IF NOT EXISTS pgcrypto"))
    # Legacy maintenance scripts attribute direct owner-role writes to actor 0.
    # Give those records a stable, disabled system identity instead of allowing
    # audit foreign keys to fail on a clean installation.
    bind.execute(sa.text("""
        INSERT INTO public.users (user_id, clerk_user_id, full_name, email, role, is_active)
        VALUES (0, 'argus-system-maintenance', 'Argus System Maintenance',
                'system-maintenance@argus.invalid', 'hr_admin', FALSE)
        ON CONFLICT (user_id) DO NOTHING
    """))
    bind.execute(sa.text("""
        DO $$ BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'argus_audit_owner') THEN
                CREATE ROLE argus_audit_owner NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT;
            END IF;
        END $$;
        -- Managed PostgreSQL providers may grant the migration login CREATEROLE
        -- without making it a superuser. Temporarily grant membership so it can
        -- assign ownership to the non-login owner role below, then revoke it
        -- before the migration completes.
        GRANT argus_audit_owner TO CURRENT_USER;
        -- Supabase places pgcrypto in `extensions`; stock PostgreSQL commonly
        -- places it in `public`. Grant the non-login verifier owner access to
        -- the installed extension schema without assuming either location.
        DO $$
        DECLARE v_crypto_schema TEXT;
        BEGIN
            SELECT n.nspname INTO v_crypto_schema
            FROM pg_extension AS e
            JOIN pg_namespace AS n ON n.oid = e.extnamespace
            WHERE e.extname = 'pgcrypto';
            IF v_crypto_schema IS NOT NULL THEN
                EXECUTE format('GRANT USAGE ON SCHEMA %I TO argus_audit_owner', v_crypto_schema);
                EXECUTE format(
                    'GRANT EXECUTE ON FUNCTION %I.hmac(bytea, bytea, text) TO argus_audit_owner',
                    v_crypto_schema
                );
            END IF;
        END $$;
        CREATE SCHEMA argus_private AUTHORIZATION argus_audit_owner;
        REVOKE ALL ON SCHEMA argus_private FROM PUBLIC;
        REVOKE CREATE ON SCHEMA public FROM PUBLIC;
        DO $$ BEGIN
            IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'hr_admin') THEN
                REVOKE ALL ON SCHEMA argus_private FROM hr_admin;
            END IF;
            IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'compliance_auditor') THEN
                REVOKE ALL ON SCHEMA argus_private FROM compliance_auditor;
            END IF;
        END $$;

        CREATE TABLE argus_private.actor_context_keys (
            key_id TEXT PRIMARY KEY CHECK (key_id ~ '^[A-Za-z0-9_-]{1,32}$'),
            key_material BYTEA NOT NULL CHECK (octet_length(key_material) >= 32),
            enabled BOOLEAN NOT NULL DEFAULT TRUE,
            created_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp()
        );
        CREATE TABLE argus_private.actor_context_nonces (
            nonce UUID PRIMARY KEY,
            transaction_id XID8 NOT NULL,
            actor_user_id INTEGER NOT NULL REFERENCES public.users(user_id),
            actor_employee_id INTEGER NOT NULL DEFAULT 0,
            db_role NAME NOT NULL,
            signature BYTEA NOT NULL CHECK (octet_length(signature) = 32),
            expires_at TIMESTAMPTZ NOT NULL,
            used_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp()
        );
        CREATE INDEX actor_context_nonces_expires_at_idx
            ON argus_private.actor_context_nonces (expires_at);
        ALTER TABLE argus_private.actor_context_keys OWNER TO argus_audit_owner;
        ALTER TABLE argus_private.actor_context_nonces OWNER TO argus_audit_owner;
    """))
    bind.execute(
        sa.text("""
            INSERT INTO argus_private.actor_context_keys (key_id, key_material, enabled)
            VALUES (:key_id, :key_material, TRUE)
            ON CONFLICT (key_id) DO UPDATE
            SET key_material = EXCLUDED.key_material, enabled = TRUE
        """),
        {"key_id": key_id, "key_material": secret},
    )

    bind.execute(sa.text(r"""
        CREATE OR REPLACE FUNCTION argus_private.verify_actor_context()
        RETURNS TABLE(actor_user_id INTEGER, actor_employee_id INTEGER)
        LANGUAGE plpgsql
        VOLATILE
        SECURITY DEFINER
        SET search_path = pg_catalog, argus_private, extensions, public, pg_temp
        AS $func$
        DECLARE
            v_version TEXT;
            v_key_id TEXT;
            v_user_text TEXT;
            v_employee_text TEXT;
            v_db_role TEXT;
            v_nonce_text TEXT;
            v_issued_text TEXT;
            v_expires_text TEXT;
            v_signature_text TEXT;
            v_user_id INTEGER;
            v_employee_id INTEGER;
            v_issued BIGINT;
            v_expires BIGINT;
            v_key BYTEA;
            v_expected BYTEA;
            v_actual BYTEA;
            v_payload TEXT;
            v_diff INTEGER := 0;
            v_i INTEGER;
            v_nonce UUID;
            v_xid XID8;
            v_existing RECORD;
            v_now BIGINT;
        BEGIN
            v_version := current_setting('argus.actor_context_version', true);
            v_key_id := current_setting('argus.actor_context_key_id', true);
            v_user_text := current_setting('argus.actor_user_id', true);
            v_employee_text := current_setting('argus.actor_employee_id', true);
            v_db_role := current_setting('argus.actor_db_role', true);
            v_nonce_text := current_setting('argus.actor_nonce', true);
            v_issued_text := current_setting('argus.actor_issued_at', true);
            v_expires_text := current_setting('argus.actor_expires_at', true);
            v_signature_text := current_setting('argus.actor_signature', true);

            IF COALESCE(v_version, '') <> '1'
                OR COALESCE(v_key_id, '') !~ '^[A-Za-z0-9_-]{1,32}$'
                OR COALESCE(v_user_text, '') !~ '^[1-9][0-9]{0,9}$'
                OR COALESCE(v_employee_text, '') !~ '^(0|[1-9][0-9]{0,9})$'
                OR COALESCE(v_db_role, '') NOT IN ('hr_admin', 'compliance_auditor')
                OR COALESCE(v_db_role, '') <> session_user::TEXT
                OR COALESCE(v_nonce_text, '') !~ '^[0-9a-fA-F-]{36}$'
                OR COALESCE(v_issued_text, '') !~ '^[0-9]{1,12}$'
                OR COALESCE(v_expires_text, '') !~ '^[0-9]{1,12}$'
                OR COALESCE(v_signature_text, '') !~ '^[0-9a-fA-F]{64}$'
            THEN
                RAISE EXCEPTION 'A valid signed actor context is required for this write'
                    USING ERRCODE = '28000';
            END IF;

            v_user_id := v_user_text::INTEGER;
            v_employee_id := v_employee_text::INTEGER;
            v_issued := v_issued_text::BIGINT;
            v_expires := v_expires_text::BIGINT;
            v_nonce := v_nonce_text::UUID;
            v_now := floor(extract(epoch FROM clock_timestamp()))::BIGINT;

            IF v_issued > v_now + 5 OR v_expires <= v_now
                OR v_expires <= v_issued OR v_expires - v_issued > 60
            THEN
                RAISE EXCEPTION 'The signed actor context is expired or outside its validity window'
                    USING ERRCODE = '28000';
            END IF;

            SELECT key_material INTO STRICT v_key
            FROM argus_private.actor_context_keys
            WHERE key_id = v_key_id AND enabled;

            v_payload := 'argus-actor-context-v1|' || v_key_id || '|'
                || v_user_id::TEXT || '|' || v_employee_id::TEXT || '|'
                || v_db_role || '|' || v_nonce::TEXT || '|'
                || v_issued::TEXT || '|' || v_expires::TEXT;
            -- Resolve pgcrypto from either Supabase's extensions schema or
            -- stock PostgreSQL's public schema via this function's pinned path.
            v_expected := hmac(convert_to(v_payload, 'UTF8'), v_key, 'sha256');
            v_actual := decode(v_signature_text, 'hex');
            FOR v_i IN 0..31 LOOP
                v_diff := v_diff | (get_byte(v_expected, v_i) # get_byte(v_actual, v_i));
            END LOOP;
            IF v_diff <> 0 THEN
                RAISE EXCEPTION 'The signed actor context failed verification'
                    USING ERRCODE = '28000';
            END IF;

            v_xid := pg_current_xact_id();
            INSERT INTO argus_private.actor_context_nonces (
                nonce, transaction_id, actor_user_id, actor_employee_id,
                db_role, signature, expires_at
            ) VALUES (
                v_nonce, v_xid, v_user_id, v_employee_id,
                v_db_role::NAME, v_actual,
                to_timestamp(v_expires::DOUBLE PRECISION)
            ) ON CONFLICT (nonce) DO NOTHING;

            SELECT n.transaction_id, n.actor_user_id, n.actor_employee_id,
                   n.db_role, n.signature
            INTO v_existing
            FROM argus_private.actor_context_nonces AS n
            WHERE n.nonce = v_nonce;

            IF v_existing.transaction_id <> v_xid
                OR v_existing.actor_user_id <> v_user_id
                OR v_existing.actor_employee_id <> v_employee_id
                OR v_existing.db_role <> v_db_role::NAME
                OR v_existing.signature <> v_actual
            THEN
                RAISE EXCEPTION 'The signed actor context nonce has already been used'
                    USING ERRCODE = '28000';
            END IF;

            RETURN QUERY SELECT v_user_id, v_employee_id;
        EXCEPTION
            WHEN NO_DATA_FOUND OR TOO_MANY_ROWS THEN
                RAISE EXCEPTION 'The signed actor context key is unavailable'
                    USING ERRCODE = '28000';
        END;
        $func$;

        ALTER FUNCTION argus_private.verify_actor_context() OWNER TO argus_audit_owner;
        REVOKE ALL ON FUNCTION argus_private.verify_actor_context() FROM PUBLIC;

        CREATE OR REPLACE FUNCTION public.trg_actor_context_guard_fn()
        RETURNS TRIGGER
        LANGUAGE plpgsql
        SECURITY DEFINER
        SET search_path = pg_catalog, argus_private, pg_temp
        AS $func$
        DECLARE
            v_actor_user_id INTEGER;
            v_actor_employee_id INTEGER;
        BEGIN
            -- Only the application login is required to present an assertion.
            -- Database-owner/maintenance credentials remain outside the runtime threat boundary.
            IF session_user::TEXT <> 'hr_admin' THEN
                IF TG_OP = 'DELETE' THEN RETURN OLD; END IF;
                RETURN NEW;
            END IF;

            SELECT actor_user_id, actor_employee_id
            INTO STRICT v_actor_user_id, v_actor_employee_id
            FROM argus_private.verify_actor_context();

            -- Replace any caller-supplied legacy actor values with verified values.
            PERFORM set_config('argus.actor_user_id', v_actor_user_id::TEXT, true);
            PERFORM set_config('argus.actor_employee_id', v_actor_employee_id::TEXT, true);
            IF TG_OP = 'DELETE' THEN RETURN OLD; END IF;
            RETURN NEW;
        END;
        $func$;
        GRANT CREATE ON SCHEMA public TO argus_audit_owner;
        ALTER FUNCTION public.trg_actor_context_guard_fn() OWNER TO argus_audit_owner;
        REVOKE CREATE ON SCHEMA public FROM argus_audit_owner;
        REVOKE ALL ON FUNCTION public.trg_actor_context_guard_fn() FROM PUBLIC;
        GRANT EXECUTE ON FUNCTION argus_private.verify_actor_context() TO argus_audit_owner;

        DROP TRIGGER IF EXISTS trg_actor_context_guard ON public.employees;
        CREATE TRIGGER trg_actor_context_guard
            BEFORE INSERT OR UPDATE OR DELETE ON public.employees
            FOR EACH ROW EXECUTE FUNCTION public.trg_actor_context_guard_fn();
        DROP TRIGGER IF EXISTS trg_actor_context_guard ON public.salary_history;
        CREATE TRIGGER trg_actor_context_guard
            BEFORE INSERT OR UPDATE OR DELETE ON public.salary_history
            FOR EACH ROW EXECUTE FUNCTION public.trg_actor_context_guard_fn();

        CREATE OR REPLACE FUNCTION argus_private.prune_actor_context_nonces()
        RETURNS BIGINT
        LANGUAGE plpgsql
        SECURITY DEFINER
        SET search_path = pg_catalog, argus_private, pg_temp
        AS $func$
        DECLARE v_deleted BIGINT;
        BEGIN
            DELETE FROM argus_private.actor_context_nonces
            WHERE expires_at < clock_timestamp() - INTERVAL '1 day';
            GET DIAGNOSTICS v_deleted = ROW_COUNT;
            RETURN v_deleted;
        END;
        $func$;
        ALTER FUNCTION argus_private.prune_actor_context_nonces() OWNER TO argus_audit_owner;
        REVOKE ALL ON FUNCTION argus_private.prune_actor_context_nonces() FROM PUBLIC;
        DO $$ BEGIN
            IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'compliance_auditor') THEN
                GRANT EXECUTE ON FUNCTION argus_private.prune_actor_context_nonces() TO compliance_auditor;
            END IF;
        END $$;
        REVOKE argus_audit_owner FROM CURRENT_USER;
    """))


def downgrade() -> None:
    """Refuse to restore spoofable actor attribution on a production database."""
    raise RuntimeError(
        "Signed actor context is a security boundary. Roll back application code only after a reviewed forward fix; do not downgrade this migration."
    )
