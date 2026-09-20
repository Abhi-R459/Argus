"""HARDEN-009: Tunable PBKDF2-HMAC-SHA256 Blind Indexing for Masked PII

Revision ID: 013_tunable_pbkdf2_blind_index
Revises: 012_checkpoint_key_id
Create Date: 2026-09-13 12:15:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '013_tunable_pbkdf2_blind_index'
down_revision: Union[str, None] = '012_checkpoint_key_id'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    is_postgres = bind.dialect.name == "postgresql"

    if is_postgres:
        op.execute(sa.text("DROP FUNCTION IF EXISTS compute_blind_index(TEXT, TEXT);"))

        # Create tunable compute_blind_index function (NIST SP 800-132 PBKDF2-HMAC-SHA256)
        op.execute(sa.text("""
        CREATE OR REPLACE FUNCTION compute_blind_index(
            p_val        TEXT,
            p_salt       TEXT,
            p_iterations INT DEFAULT 1000
        )
        RETURNS TEXT
        LANGUAGE plpgsql
        IMMUTABLE
        AS $func$
        DECLARE
            v_u     BYTEA;
            v_t     BYTEA;
            i       INT;
            j       INT;
            b_t     INT;
            b_u     INT;
            v_iters INT;
        BEGIN
            IF p_val IS NULL OR p_val = '' THEN
                RETURN NULL;
            END IF;

            v_iters := COALESCE(p_iterations, 1000);
            IF v_iters <= 1 THEN
                RETURN encode(hmac(p_val::bytea, p_salt::bytea, 'sha256'), 'hex');
            END IF;

            -- PBKDF2-HMAC-SHA256 (NIST SP 800-132 / RFC 8018)
            -- U_1 = HMAC(salt || 0x00000001, key=val)
            v_u := hmac(p_salt::bytea || decode('00000001', 'hex'), p_val::bytea, 'sha256');
            v_t := v_u;

            FOR i IN 2..v_iters LOOP
                v_u := hmac(v_u, p_val::bytea, 'sha256');
                FOR j IN 0..31 LOOP
                    b_t := get_byte(v_t, j);
                    b_u := get_byte(v_u, j);
                    v_t := set_byte(v_t, j, b_t # b_u);
                END LOOP;
            END LOOP;

            RETURN encode(v_t, 'hex');
        END;
        $func$;
        """))

        # Update mask_employee_payload function to support tunable iterations
        op.execute(sa.text("""
        CREATE OR REPLACE FUNCTION mask_employee_payload(p_payload JSONB)
        RETURNS JSONB
        LANGUAGE plpgsql
        IMMUTABLE
        AS $func$
        DECLARE
            v_salt         TEXT;
            v_raw_nid      TEXT;
            v_blind_index  TEXT := NULL;
            v_iters_str    TEXT;
            v_iters        INT := 1000;
        BEGIN
            BEGIN
                v_salt := current_setting('argus.audit_salt', true);
            EXCEPTION WHEN OTHERS THEN
                v_salt := NULL;
            END;
            IF v_salt IS NULL OR v_salt = '' THEN
                v_salt := 'argus_default_blind_index_salt_2026';
            END IF;

            BEGIN
                v_iters_str := current_setting('argus.blind_index_iterations', true);
                v_iters := v_iters_str::INT;
            EXCEPTION WHEN OTHERS THEN
                v_iters := 1000;
            END;
            IF v_iters IS NULL OR v_iters < 1 THEN
                v_iters := 1000;
            END IF;

            IF p_payload ? 'national_id' AND p_payload->>'national_id' IS NOT NULL AND p_payload->>'national_id' != '[REDACTED]' THEN
                v_raw_nid := p_payload->>'national_id';
            ELSIF p_payload ? 'national_id_encrypted' AND p_payload->>'national_id_encrypted' LIKE '\\x%' THEN
                BEGIN
                    v_raw_nid := convert_from(decode(substring(p_payload->>'national_id_encrypted' from 3), 'hex'), 'UTF8');
                EXCEPTION WHEN OTHERS THEN
                    v_raw_nid := NULL;
                END;
            END IF;

            IF v_raw_nid IS NOT NULL AND v_raw_nid != '' THEN
                v_blind_index := compute_blind_index(v_raw_nid, v_salt, v_iters);
            END IF;

            p_payload := p_payload - 'national_id_encrypted';
            p_payload := p_payload - 'contact_info_encrypted';
            p_payload := p_payload - 'national_id';
            p_payload := p_payload - 'contact_info';

            p_payload := p_payload
                || jsonb_build_object('national_id_encrypted', '[REDACTED]')
                || jsonb_build_object('contact_info_encrypted', '[REDACTED]');

            IF v_blind_index IS NOT NULL THEN
                p_payload := p_payload || jsonb_build_object('national_id_blind_index', v_blind_index);
            END IF;

            RETURN p_payload;
        END;
        $func$;
        """))


def downgrade() -> None:
    bind = op.get_bind()
    is_postgres = bind.dialect.name == "postgresql"

    if is_postgres:
        op.execute(sa.text("DROP FUNCTION IF EXISTS compute_blind_index(TEXT, TEXT, INT);"))

        # Revert to legacy HMAC compute_blind_index
        op.execute(sa.text("""
        CREATE OR REPLACE FUNCTION compute_blind_index(
            p_val  TEXT,
            p_salt TEXT
        )
        RETURNS TEXT
        LANGUAGE plpgsql
        IMMUTABLE
        AS $func$
        BEGIN
            IF p_val IS NULL OR p_val = '' THEN
                RETURN NULL;
            END IF;
            RETURN encode(hmac(p_val::bytea, p_salt::bytea, 'sha256'), 'hex');
        END;
        $func$;
        """))

        # Revert mask_employee_payload
        op.execute(sa.text("""
        CREATE OR REPLACE FUNCTION mask_employee_payload(p_payload JSONB)
        RETURNS JSONB
        LANGUAGE plpgsql
        IMMUTABLE
        AS $func$
        DECLARE
            v_salt         TEXT;
            v_raw_nid      TEXT;
            v_blind_index  TEXT := NULL;
        BEGIN
            BEGIN
                v_salt := current_setting('argus.audit_salt', true);
            EXCEPTION WHEN OTHERS THEN
                v_salt := NULL;
            END;
            IF v_salt IS NULL OR v_salt = '' THEN
                v_salt := 'argus_default_blind_index_salt_2026';
            END IF;

            IF p_payload ? 'national_id' AND p_payload->>'national_id' IS NOT NULL AND p_payload->>'national_id' != '[REDACTED]' THEN
                v_raw_nid := p_payload->>'national_id';
            ELSIF p_payload ? 'national_id_encrypted' AND p_payload->>'national_id_encrypted' LIKE '\\x%' THEN
                BEGIN
                    v_raw_nid := convert_from(decode(substring(p_payload->>'national_id_encrypted' from 3), 'hex'), 'UTF8');
                EXCEPTION WHEN OTHERS THEN
                    v_raw_nid := NULL;
                END;
            END IF;

            IF v_raw_nid IS NOT NULL AND v_raw_nid != '' THEN
                v_blind_index := compute_blind_index(v_raw_nid, v_salt);
            END IF;

            p_payload := p_payload - 'national_id_encrypted';
            p_payload := p_payload - 'contact_info_encrypted';
            p_payload := p_payload - 'national_id';
            p_payload := p_payload - 'contact_info';

            p_payload := p_payload
                || jsonb_build_object('national_id_encrypted', '[REDACTED]')
                || jsonb_build_object('contact_info_encrypted', '[REDACTED]');

            IF v_blind_index IS NOT NULL THEN
                p_payload := p_payload || jsonb_build_object('national_id_blind_index', v_blind_index);
            END IF;

            RETURN p_payload;
        END;
        $func$;
        """))
