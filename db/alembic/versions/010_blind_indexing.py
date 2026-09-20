"""BLIND-001: HMAC Blind Indexing for Masked PII

Revision ID: 010_blind_indexing
Revises: 009_stored_routines
Create Date: 2026-09-12 10:45:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '010_blind_indexing'
down_revision: Union[str, None] = '009_stored_routines'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    is_postgres = bind.dialect.name == "postgresql"

    if is_postgres:
        # 1. Ensure pgcrypto extension is available
        op.execute(sa.text("CREATE EXTENSION IF NOT EXISTS pgcrypto;"))

        # 2. Create compute_blind_index function
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

        # 3. Update mask_employee_payload function
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

        # 4. Create functional B-tree expression index on audit_log
        op.execute(sa.text("""
        CREATE INDEX IF NOT EXISTS idx_audit_log_nid_blind
        ON audit_log ((new_value->>'national_id_blind_index'))
        WHERE new_value->>'national_id_blind_index' IS NOT NULL;
        """))
    else:
        # SQLite compatibility for in-memory unit tests
        try:
            op.execute(sa.text("CREATE INDEX IF NOT EXISTS idx_audit_log_nid_blind ON audit_log (json_extract(new_value, '$.national_id_blind_index'));"))
        except Exception:
            pass


def downgrade() -> None:
    bind = op.get_bind()
    is_postgres = bind.dialect.name == "postgresql"

    if is_postgres:
        op.execute(sa.text("DROP INDEX IF EXISTS idx_audit_log_nid_blind;"))
        op.execute(sa.text("""
        CREATE OR REPLACE FUNCTION mask_employee_payload(p_payload JSONB)
        RETURNS JSONB
        LANGUAGE plpgsql
        IMMUTABLE
        AS $func$
        BEGIN
            p_payload := p_payload - 'national_id_encrypted';
            p_payload := p_payload - 'contact_info_encrypted';
            p_payload := p_payload
                || jsonb_build_object('national_id_encrypted', '[REDACTED]')
                || jsonb_build_object('contact_info_encrypted', '[REDACTED]');
            RETURN p_payload;
        END;
        $func$;
        """))
        op.execute(sa.text("DROP FUNCTION IF EXISTS compute_blind_index(TEXT, TEXT);"))
    else:
        try:
            op.execute(sa.text("DROP INDEX IF EXISTS idx_audit_log_nid_blind;"))
        except Exception:
            pass
