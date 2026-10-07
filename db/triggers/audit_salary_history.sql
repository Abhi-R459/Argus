/*
 * DB-008: Hash-Chaining AFTER Trigger on salary_history
 * DB-019: Runtime HR actor attribution is enforced by the signed-context
 *         BEFORE trigger installed by migration 019_signed_actor_context.
 *
 * Mirrors the pattern established in audit_employees.sql but fires on
 * the salary_history table.  Salary operations are always classified as
 * WARNING severity (see assign_severity() in audit_employees.sql).
 *
 * The chain is SHARED with the employees trigger — both tables append to
 * the same audit_log / chain_state singleton, so the hash chain is
 * contiguous across all audited tables.
 *
 * Serialization contract (SETUP-002):
 *   sequence_id || '|' || actor_user_id || '|' || action || '|' ||
 *   'salary_history' || '|' || row_id   || '|' ||
 *   COALESCE(old_value::TEXT, 'null')   || '|' ||
 *   COALESCE(new_value::TEXT, 'null')   || '|' || created_at
 *
 * NOTE: assign_severity() and mask_employee_payload() helpers are already
 * defined in audit_employees.sql and are reused here.
 */

-- ---------------------------------------------------------------------------
-- Trigger Function: trg_salary_history_hash_chain_fn
-- ---------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION trg_salary_history_hash_chain_fn()
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
    v_employee_id      INT;
    v_action           TEXT;
BEGIN
    -- -----------------------------------------------------------------------
    -- Acquire exclusive row-level lock on the chain_state singleton.
    -- This serializes concurrent salary updates into a strict linear chain.
    -- -----------------------------------------------------------------------
    SELECT tail_hash, tail_sequence_id + 1
    INTO   v_prev_hash, v_next_seq_id
    FROM   chain_state
    WHERE  id = 1
    FOR UPDATE;

    -- Resolve actor from session variable set by the API layer.
    BEGIN
        v_actor_user_id := current_setting('argus.actor_user_id')::INT;
    EXCEPTION WHEN OTHERS THEN
        v_actor_user_id := 0;
    END;

    v_action := TG_OP;

    IF TG_OP = 'DELETE' THEN
        v_row_id      := OLD.salary_history_id;
        v_employee_id := OLD.employee_id;
    ELSE
        v_row_id      := NEW.salary_history_id;
        v_employee_id := NEW.employee_id;
    END IF;

    -- -----------------------------------------------------------------------
    -- Build JSONB payloads.
    -- salary_history has no encrypted columns, so to_jsonb() is used directly.
    -- -----------------------------------------------------------------------
    IF TG_OP IN ('UPDATE', 'DELETE') THEN
        v_old_payload := to_jsonb(OLD);
    ELSE
        v_old_payload := NULL;
    END IF;

    IF TG_OP IN ('INSERT', 'UPDATE') THEN
        v_new_payload := to_jsonb(NEW);
    ELSE
        v_new_payload := NULL;
    END IF;

    -- Salary operations are always WARNING severity (Decision: DB-009 rules).
    v_severity := assign_severity(v_action, 'salary_history');

    v_created_at := CURRENT_TIMESTAMP;

    -- -----------------------------------------------------------------------
    -- Compute SHA-256 entry hash (pgcrypto / Decision #11).
    -- -----------------------------------------------------------------------
    v_serialized :=
        v_next_seq_id::TEXT                          || '|' ||
        v_actor_user_id::TEXT                        || '|' ||
        v_action                                     || '|' ||
        'salary_history'                             || '|' ||
        v_row_id::TEXT                               || '|' ||
        COALESCE(v_old_payload::TEXT, 'null')        || '|' ||
        COALESCE(v_new_payload::TEXT, 'null')        || '|' ||
        v_created_at::TEXT;

    v_entry_hash := encode(
        digest(v_serialized || v_prev_hash, 'sha256'),
        'hex'
    );

    -- -----------------------------------------------------------------------
    -- Append to audit_log.
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
        v_employee_id,
        v_action,
        'salary_history',
        v_row_id,
        v_old_payload,
        v_new_payload,
        v_severity,
        v_entry_hash,
        v_prev_hash,
        v_created_at
    );

    -- -----------------------------------------------------------------------
    -- Advance chain_state tail.
    -- -----------------------------------------------------------------------
    UPDATE chain_state
    SET    tail_hash        = v_entry_hash,
           tail_sequence_id = v_next_seq_id
    WHERE  id = 1;

    IF TG_OP = 'DELETE' THEN
        RETURN OLD;
    ELSE
        RETURN NEW;
    END IF;
END;
$$;

-- ---------------------------------------------------------------------------
-- Trigger: trg_salary_history_hash_chain
-- ---------------------------------------------------------------------------
DROP TRIGGER IF EXISTS trg_salary_history_hash_chain ON salary_history;

CREATE TRIGGER trg_salary_history_hash_chain
    AFTER INSERT OR UPDATE OR DELETE
    ON salary_history
    FOR EACH ROW
    EXECUTE FUNCTION trg_salary_history_hash_chain_fn();
