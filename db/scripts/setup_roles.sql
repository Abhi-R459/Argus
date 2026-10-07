-- Argus PostgreSQL Role Setup & Permissions Initialization Script (DB-006, DB-015)
-- Run as the database owner against the database selected by the connection URL.

-- 1. Create Roles if they do not exist
DO $$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'hr_admin') THEN
        CREATE ROLE hr_admin WITH LOGIN;
    END IF;

    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'compliance_auditor') THEN
        CREATE ROLE compliance_auditor WITH LOGIN;
    END IF;
END $$;

-- ============================================================================
-- DB-015: Finalize GRANT/REVOKE Permissions
-- ============================================================================

-- 2. HR Admin — Full CRUD on core entity tables, read-only on audit tables
DO $$
DECLARE
    v_database_name NAME := current_database();
BEGIN
    EXECUTE format('GRANT CONNECT ON DATABASE %I TO hr_admin', v_database_name);
    EXECUTE format('GRANT CONNECT ON DATABASE %I TO compliance_auditor', v_database_name);
END $$;
GRANT USAGE ON SCHEMA public TO hr_admin;

-- Entity tables (HR Admin manages employee data)
GRANT SELECT, INSERT, UPDATE ON departments TO hr_admin;
GRANT SELECT, INSERT, UPDATE ON roles TO hr_admin;
GRANT SELECT, INSERT, UPDATE ON users TO hr_admin;
GRANT SELECT, INSERT, UPDATE ON employees TO hr_admin;
GRANT SELECT, INSERT, UPDATE ON salary_history TO hr_admin;

-- HR Admin may READ audit records for their own actions but CANNOT modify or forge them.
-- Append-only enforcement: REVOKE INSERT, UPDATE, DELETE, TRUNCATE (Decisions #12, #33).
-- All audit_log writes MUST flow strictly through SECURITY DEFINER triggers owned by postgres.
REVOKE ALL PRIVILEGES ON audit_log FROM PUBLIC;
REVOKE INSERT, UPDATE, DELETE, TRUNCATE ON audit_log FROM hr_admin, compliance_auditor, PUBLIC;
GRANT SELECT ON audit_log TO hr_admin;

-- Suspicious flags: HR Admin can read flags but cannot modify audit records.
GRANT SELECT ON suspicious_activity_flags TO hr_admin;

-- Views
GRANT SELECT ON v_employee_directory TO hr_admin;
GRANT SELECT ON v_compliance_overview TO hr_admin;

-- Sequence access for auto-increment columns
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO hr_admin;

-- 3. Compliance Auditor — Read-only on all audit and chain tables
GRANT USAGE ON SCHEMA public TO compliance_auditor;

-- These are the only public-schema routines directly invoked by the Auditor
-- API; broad PUBLIC execution is revoked on Supabase.
GRANT EXECUTE ON FUNCTION public.reconstruct_employee_state(INTEGER, TIMESTAMPTZ)
    TO compliance_auditor;
GRANT EXECUTE ON PROCEDURE public.refresh_suspicious_activity_flags()
    TO compliance_auditor;

-- Audit chain tables (read-only — cannot modify or forge any audit data)
REVOKE INSERT, UPDATE, DELETE, TRUNCATE ON audit_log FROM compliance_auditor;
REVOKE INSERT, UPDATE, DELETE, TRUNCATE ON audit_log FROM hr_admin;
GRANT SELECT ON audit_log TO compliance_auditor;

GRANT SELECT, UPDATE ON suspicious_activity_flags TO compliance_auditor;
GRANT SELECT ON chain_state TO compliance_auditor;
GRANT SELECT ON chain_checkpoints TO compliance_auditor;
-- HR can append checkpoints only through the role-checked API. Updates/deletes
-- remain unavailable; signatures and actor metadata are written atomically.
GRANT INSERT ON chain_checkpoints TO hr_admin;
GRANT USAGE, SELECT ON SEQUENCE chain_checkpoints_checkpoint_id_seq TO hr_admin;
GRANT INSERT ON security_audit_events TO hr_admin;
GRANT USAGE, SELECT ON SEQUENCE security_audit_events_event_id_seq TO hr_admin;
REVOKE UPDATE, DELETE, TRUNCATE ON chain_checkpoints FROM hr_admin;
REVOKE UPDATE, DELETE, TRUNCATE ON security_audit_events FROM hr_admin;
GRANT SELECT ON backups TO compliance_auditor;

-- Metadata tables for audit trail actor & time-travel resolution
GRANT SELECT ON users TO compliance_auditor;
GRANT SELECT ON departments, roles, salary_history TO compliance_auditor;

-- Views
GRANT SELECT ON v_compliance_overview TO compliance_auditor;
REVOKE SELECT ON v_employee_directory FROM compliance_auditor;
GRANT SELECT ON v_compliance_employee_directory TO compliance_auditor;

-- Privacy-preserving Audit-the-Auditor telemetry. Auditor sessions may append
-- and read events, but cannot rewrite or erase historical event records.
GRANT SELECT, INSERT ON security_audit_events TO compliance_auditor;
REVOKE UPDATE, DELETE, TRUNCATE ON security_audit_events FROM compliance_auditor;
GRANT USAGE, SELECT ON SEQUENCE security_audit_events_event_id_seq TO compliance_auditor;
GRANT SELECT, INSERT ON suspicious_activity_reviews TO compliance_auditor;
REVOKE UPDATE, DELETE, TRUNCATE ON suspicious_activity_reviews FROM compliance_auditor;
GRANT USAGE, SELECT ON SEQUENCE suspicious_activity_reviews_review_id_seq TO compliance_auditor;

-- Allow the API's scheduled janitor to remove expired nonce records through a
-- narrow SECURITY DEFINER function; the auditor cannot read or edit the table.
-- The nonce table and its SECURITY DEFINER janitor belong to the isolated
-- argus_audit_owner role. On managed PostgreSQL (including Supabase), the
-- migration login may have CREATEROLE without owning that schema or function,
-- so it cannot grant USAGE or EXECUTE directly. Temporarily assume the owner
-- role for these narrow grants, then immediately remove the membership.
GRANT argus_audit_owner TO CURRENT_USER;
SET ROLE argus_audit_owner;
GRANT USAGE ON SCHEMA argus_private TO compliance_auditor;
GRANT EXECUTE ON FUNCTION argus_private.prune_actor_context_nonces() TO compliance_auditor;
RESET ROLE;
REVOKE argus_audit_owner FROM CURRENT_USER;

-- Compliance Auditor has NO access to raw employee data (PII protection)
-- They access employee details only through v_employee_directory view.
