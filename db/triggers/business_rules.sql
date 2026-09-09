/*
 * DB-012: Salary Decrease >30% Trigger
 * DB-013: National ID Immutability Trigger
 * DB-014: Self-Salary Modification Block Trigger
 *
 * These are BEFORE triggers that enforce business rules BEFORE the data
 * change is committed.  They are separate from the AFTER hash-chain triggers.
 *
 * Constraints:
 *   - DB-012: A salary insert that drops pay by more than 30% vs the current
 *             latest salary for that employee is blocked with RAISE EXCEPTION.
 *   - DB-013: Any UPDATE that changes national_id_encrypted is blocked.
 *   - DB-014: An employee cannot insert a salary record for themselves.
 *             The API must SET LOCAL argus.actor_employee_id = <emp_id>;
 *             before the INSERT.
 */

-- ---------------------------------------------------------------------------
-- DB-013: National ID Immutability BEFORE UPDATE trigger
-- ---------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION trg_employees_national_id_immutable_fn()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    -- Block any attempt to change national_id_encrypted regardless of role.
    -- The encrypted bytes are compared directly; any byte difference is blocked.
    IF NEW.national_id_encrypted IS DISTINCT FROM OLD.national_id_encrypted THEN
        RAISE EXCEPTION 'national_id_immutable: national_id_encrypted cannot be changed after creation'
            USING ERRCODE = 'P0001';
    END IF;
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_employees_national_id_immutable ON employees;

CREATE TRIGGER trg_employees_national_id_immutable
    BEFORE UPDATE
    ON employees
    FOR EACH ROW
    EXECUTE FUNCTION trg_employees_national_id_immutable_fn();

-- ---------------------------------------------------------------------------
-- DB-012: Salary Decrease >30% BEFORE INSERT trigger
-- ---------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION trg_salary_history_decrease_check_fn()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
DECLARE
    v_current_salary NUMERIC(12, 2);
BEGIN
    -- Fetch the most recent salary amount for this employee.
    -- If no previous record exists this is the first salary insert → allow it.
    SELECT amount
    INTO   v_current_salary
    FROM   salary_history
    WHERE  employee_id = NEW.employee_id
    ORDER  BY effective_date DESC, salary_history_id DESC
    LIMIT  1;

    -- No previous salary → first record, always permitted.
    IF v_current_salary IS NULL THEN
        RETURN NEW;
    END IF;

    -- Block if new salary is less than 70% of the current salary
    -- (i.e., a decrease of more than 30%).
    IF NEW.amount < (v_current_salary * 0.70) THEN
        RAISE EXCEPTION
            'salary_decrease_exceeded: new salary (%) is more than 30%% below current salary (%)',
            NEW.amount, v_current_salary
            USING ERRCODE = 'P0002';
    END IF;

    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_salary_history_decrease_check ON salary_history;

CREATE TRIGGER trg_salary_history_decrease_check
    BEFORE INSERT
    ON salary_history
    FOR EACH ROW
    EXECUTE FUNCTION trg_salary_history_decrease_check_fn();

-- ---------------------------------------------------------------------------
-- DB-014: Self-Salary Modification Block BEFORE INSERT trigger
-- ---------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION trg_salary_history_self_block_fn()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
DECLARE
    v_actor_employee_id INT;
BEGIN
    -- Read the actor's employee_id from the session-local variable.
    -- The API layer must execute:
    --   SET LOCAL argus.actor_employee_id = <employee_id>;
    -- If the variable is not set, we cannot determine the actor → allow through
    -- (superuser / system operations are trusted at the DB layer).
    BEGIN
        v_actor_employee_id := current_setting('argus.actor_employee_id')::INT;
    EXCEPTION WHEN OTHERS THEN
        RETURN NEW;  -- Variable not set → bypass check
    END;

    -- Block if the actor is modifying their own salary record.
    IF v_actor_employee_id = NEW.employee_id THEN
        RAISE EXCEPTION
            'self_modification_blocked: employee (id=%) cannot modify their own salary record',
            v_actor_employee_id
            USING ERRCODE = 'P0003';
    END IF;

    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_salary_history_self_block ON salary_history;

CREATE TRIGGER trg_salary_history_self_block
    BEFORE INSERT
    ON salary_history
    FOR EACH ROW
    EXECUTE FUNCTION trg_salary_history_self_block_fn();
