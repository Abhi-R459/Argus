/*
 * DB-007: Hash-Chaining AFTER Trigger on employees
 * DB-009: Severity Assignment Logic (integrated)
 * DB-010: Masked Audit Payload (integrated)
 * DB-019: Runtime HR actor attribution is enforced by the signed-context
 *         BEFORE trigger installed by migration 019_signed_actor_context.
 *
 * This trigger fires AFTER every INSERT, UPDATE, or DELETE on the `employees`
 * table.  It is the heart of Argus's tamper-evident audit trail:
 *
 *   1.  Acquires an EXCLUSIVE row-level lock on `chain_state` (id = 1) so that
 *       concurrent transactions cannot corrupt the hash chain.
 *   2.  Builds redacted JSONB before/after payloads (national_id_encrypted and
 *       contact_info_encrypted are replaced with '[REDACTED]').
 *   3.  Computes a SHA-256 entry hash over the serialized payload concatenated
 *       with the previous chain tail (SETUP-002 serialization contract).
 *   4.  Appends the audit entry to `audit_log`.
 *   5.  Updates `chain_state.tail_hash` to the new entry hash.
 *
 * Serialization contract (SETUP-002):
 *   sequence_id::TEXT || '|' || actor_user_id::TEXT || '|' || action || '|' ||
 *   table_name || '|' || row_id::TEXT || '|' ||
 *   COALESCE(old_value::TEXT, 'null') || '|' ||
 *   COALESCE(new_value::TEXT, 'null') || '|' || created_at::TEXT
 */

-- ---------------------------------------------------------------------------
-- Helper: compute_blind_index (BLIND-001 & HARDEN-009)
-- ---------------------------------------------------------------------------
-- Computes a tunable PBKDF2-HMAC-SHA256 blind index (NIST SP 800-132) over a
-- sensitive text value using a salt and work factor iteration count.
-- If p_iterations <= 1, falls back to single-round HMAC-SHA256.
-- Returns a 64-character lowercase hexadecimal hash.
-- ---------------------------------------------------------------------------
DROP FUNCTION IF EXISTS compute_blind_index(TEXT, TEXT);

CREATE OR REPLACE FUNCTION compute_blind_index(
    p_val        TEXT,
    p_salt       TEXT,
    p_iterations INT DEFAULT 1000
)
RETURNS TEXT
LANGUAGE plpgsql
IMMUTABLE
AS $$
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
$$;

-- ---------------------------------------------------------------------------
-- Helper: mask_employee_payload
-- ---------------------------------------------------------------------------
-- Removes raw encrypted bytes from a JSONB employee payload by replacing
-- national_id_encrypted and contact_info_encrypted with '[REDACTED]'.
-- Also computes and injects 'national_id_blind_index' via compute_blind_index
-- using the session salt (or default) so masked records remain searchable.
-- ---------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION mask_employee_payload(p_payload JSONB)
RETURNS JSONB
LANGUAGE plpgsql
STABLE
AS $$
DECLARE
    v_salt         TEXT;
    v_raw_nid      TEXT;
    v_blind_index  TEXT := NULL;
    v_supplied_blind_index TEXT;
    v_iters_str    TEXT;
    v_iters        INT := 1000;
BEGIN
    BEGIN
        v_salt := current_setting('argus.audit_salt', true);
    EXCEPTION WHEN OTHERS THEN
        v_salt := NULL;
    END;
    IF v_salt IS NULL OR v_salt = '' THEN
        RAISE EXCEPTION 'AUDIT_SALT must be configured for employee audit writes';
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

    BEGIN
        v_supplied_blind_index := current_setting('argus.employee_national_id_blind_index', true);
    EXCEPTION WHEN OTHERS THEN
        v_supplied_blind_index := NULL;
    END;
    IF v_supplied_blind_index ~ '^[0-9a-f]{64}$' THEN
        v_blind_index := v_supplied_blind_index;
    END IF;

    IF p_payload ? 'national_id' AND p_payload->>'national_id' IS NOT NULL AND p_payload->>'national_id' != '[REDACTED]' THEN
        v_raw_nid := p_payload->>'national_id';
    ELSIF p_payload ? 'national_id_encrypted' AND p_payload->>'national_id_encrypted' LIKE '\x%' THEN
        BEGIN
            v_raw_nid := convert_from(decode(substring(p_payload->>'national_id_encrypted' from 3), 'hex'), 'UTF8');
        EXCEPTION WHEN OTHERS THEN
            v_raw_nid := NULL;
        END;
    END IF;

    IF v_blind_index IS NULL AND v_raw_nid IS NOT NULL AND v_raw_nid != '' THEN
        v_blind_index := compute_blind_index(v_raw_nid, v_salt, v_iters);
    END IF;

    -- Replace sensitive keys with a redaction marker
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
$$;

-- ---------------------------------------------------------------------------
-- Helper: assign_severity
-- ---------------------------------------------------------------------------
-- Returns an audit severity level based on the operation type and table.
--
-- Rules:
--   DELETE on any table      → CRITICAL
--   Any op on salary_history → WARNING   (salary changes are high-risk)
--   Everything else          → INFO
-- ---------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION assign_severity(
    p_action     TEXT,
    p_table_name TEXT
)
RETURNS TEXT
LANGUAGE plpgsql
IMMUTABLE
AS $$
BEGIN
    IF p_action = 'DELETE' THEN
        RETURN 'CRITICAL';
    END IF;

    IF p_table_name = 'salary_history' THEN
        RETURN 'WARNING';
    END IF;

    RETURN 'INFO';
END;
$$;

-- ---------------------------------------------------------------------------
-- Trigger Function: trg_employees_hash_chain_fn
-- ---------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION trg_employees_hash_chain_fn()
RETURNS TRIGGER
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog, public, pg_temp
AS $$
DECLARE
    v_prev_hash        CHAR(64);
    v_next_seq_id      BIGINT;
    v_actor_user_id    INT;
    v_old_payload      JSONB;
    v_new_payload      JSONB;
    v_created_at       TIMESTAMPTZ;
    v_serialized       TEXT;
    v_entry_hash       CHAR(64);
    v_severity         TEXT;
    v_row_id           INT;
    v_action           TEXT;
BEGIN
    -- -----------------------------------------------------------------------
    -- Step 2.A.4 — Acquire exclusive row-level lock on chain_state singleton.
    -- This serializes all concurrent hash-chain writes; no two transactions
    -- can hold this lock simultaneously (Two-Phase Locking, Decision #2).
    -- -----------------------------------------------------------------------
    SELECT tail_hash, tail_sequence_id + 1
    INTO   v_prev_hash, v_next_seq_id
    FROM   chain_state
    WHERE  id = 1
    FOR UPDATE;

    -- -----------------------------------------------------------------------
    -- Resolve actor: read from a session-local variable set by the API.
    -- Falls back to 0 (system/superuser) when the variable is not set.
    -- The API layer MUST execute: SET LOCAL argus.actor_user_id = <user_id>;
    -- -----------------------------------------------------------------------
    BEGIN
        v_actor_user_id := current_setting('argus.actor_user_id')::INT;
    EXCEPTION WHEN OTHERS THEN
        v_actor_user_id := 0;  -- superuser / direct-psql fallback
    END;

    -- Determine DML action and primary key
    v_action := TG_OP;

    IF TG_OP = 'DELETE' THEN
        v_row_id := OLD.employee_id;
    ELSE
        v_row_id := NEW.employee_id;
    END IF;

    -- -----------------------------------------------------------------------
    -- Step 2.A.2 & 2.A.3 — Build masked JSONB payloads (DB-010).
    -- Exclude encrypted columns so raw cipher text never enters audit_log.
    -- -----------------------------------------------------------------------
    IF TG_OP IN ('UPDATE', 'DELETE') THEN
        v_old_payload := mask_employee_payload(to_jsonb(OLD));
    ELSE
        v_old_payload := NULL;
    END IF;

    IF TG_OP IN ('INSERT', 'UPDATE') THEN
        v_new_payload := mask_employee_payload(to_jsonb(NEW));
    ELSE
        v_new_payload := NULL;
    END IF;

    -- -----------------------------------------------------------------------
    -- Step 2.C — Assign severity (DB-009).
    -- -----------------------------------------------------------------------
    v_severity := assign_severity(v_action, 'employees');

    -- Capture wall-clock timestamp for deterministic hash serialization
    v_created_at := CURRENT_TIMESTAMP;

    -- -----------------------------------------------------------------------
    -- Step 2.A.5 — Compute SHA-256 entry hash via pgcrypto (Decision #11).
    --
    -- Serialization format (SETUP-002):
    --   sequence_id || '|' || actor_user_id || '|' || action || '|' ||
    --   table_name  || '|' || row_id        || '|' || old_value (or 'null') ||
    --   '|' || new_value (or 'null') || '|' || created_at
    -- -----------------------------------------------------------------------
    v_serialized :=
        v_next_seq_id::TEXT          || '|' ||
        v_actor_user_id::TEXT        || '|' ||
        v_action                     || '|' ||
        'employees'                  || '|' ||
        v_row_id::TEXT               || '|' ||
        COALESCE(v_old_payload::TEXT, 'null') || '|' ||
        COALESCE(v_new_payload::TEXT, 'null') || '|' ||
        v_created_at::TEXT;

    v_entry_hash := encode(
        digest(v_serialized || v_prev_hash, 'sha256'),
        'hex'
    );

    -- -----------------------------------------------------------------------
    -- Step 2.A.6 — Append to audit_log.
    -- -----------------------------------------------------------------------
    INSERT INTO audit_log (
        sequence_id,
        actor_user_id,
        employee_id,
        action,
        table_name,
        row_id,
        old_value,
        new_value,
        severity,
        entry_hash,
        previous_hash,
        created_at
    ) VALUES (
        v_next_seq_id,
        v_actor_user_id,
        v_row_id,
        v_action,
        'employees',
        v_row_id,
        v_old_payload,
        v_new_payload,
        v_severity,
        v_entry_hash,
        v_prev_hash,
        v_created_at
    );

    -- -----------------------------------------------------------------------
    -- Step 2.A.7 — Advance chain_state tail to the new entry.
    -- -----------------------------------------------------------------------
    UPDATE chain_state
    SET    tail_hash        = v_entry_hash,
           tail_sequence_id = v_next_seq_id
    WHERE  id = 1;

    -- Return the appropriate row to PostgreSQL
    IF TG_OP = 'DELETE' THEN
        RETURN OLD;
    ELSE
        RETURN NEW;
    END IF;
END;
$$;

-- ---------------------------------------------------------------------------
-- Trigger: trg_employees_hash_chain
-- ---------------------------------------------------------------------------
-- Fires AFTER every INSERT, UPDATE, or DELETE on employees (Decision #7).
-- One trigger handles all three operations so the chain is always updated.
-- ---------------------------------------------------------------------------
DROP TRIGGER IF EXISTS trg_employees_hash_chain ON employees;

CREATE TRIGGER trg_employees_hash_chain
    AFTER INSERT OR UPDATE OR DELETE
    ON employees
    FOR EACH ROW
    EXECUTE FUNCTION trg_employees_hash_chain_fn();
