-- Argus PostgreSQL Role Setup & Permissions Initialization Script (DB-006, DB-015)
-- Run this as superuser (postgres) against the argus database.

-- 1. Create Roles if they do not exist
DO $$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'hr_admin') THEN
        CREATE ROLE hr_admin WITH LOGIN PASSWORD 'hr_admin_pass';
    END IF;

    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'compliance_auditor') THEN
        CREATE ROLE compliance_auditor WITH LOGIN PASSWORD 'auditor_pass';
    END IF;
END $$;

-- ============================================================================
-- DB-015: Finalize GRANT/REVOKE Permissions
-- ============================================================================

-- 2. HR Admin — Full CRUD on core entity tables, read-only on audit tables
GRANT CONNECT ON DATABASE argus TO hr_admin;
GRANT USAGE ON SCHEMA public TO hr_admin;

-- Entity tables (HR Admin manages employee data)
GRANT SELECT, INSERT, UPDATE ON departments TO hr_admin;
GRANT SELECT, INSERT, UPDATE ON roles TO hr_admin;
GRANT SELECT, INSERT, UPDATE ON users TO hr_admin;
GRANT SELECT, INSERT, UPDATE ON employees TO hr_admin;
GRANT SELECT, INSERT, UPDATE ON salary_history TO hr_admin;

-- HR Admin may READ audit records for their own actions but CANNOT modify them.
-- Append-only enforcement: REVOKE UPDATE, DELETE (Decision #12).
GRANT SELECT ON audit_log TO hr_admin;
REVOKE UPDATE, DELETE ON audit_log FROM hr_admin;

-- Suspicious flags: HR Admin can read flags but cannot modify audit records.
GRANT SELECT ON suspicious_activity_flags TO hr_admin;

-- Views
GRANT SELECT ON v_employee_directory TO hr_admin;
GRANT SELECT ON v_compliance_overview TO hr_admin;

-- Sequence access for auto-increment columns
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO hr_admin;

-- 3. Compliance Auditor — Read-only on all audit and chain tables
GRANT CONNECT ON DATABASE argus TO compliance_auditor;
GRANT USAGE ON SCHEMA public TO compliance_auditor;

-- Audit chain tables (read-only — cannot modify any audit data)
GRANT SELECT ON audit_log TO compliance_auditor;
REVOKE INSERT, UPDATE, DELETE ON audit_log FROM compliance_auditor;

GRANT SELECT ON suspicious_activity_flags TO compliance_auditor;
GRANT SELECT ON chain_state TO compliance_auditor;
GRANT SELECT ON chain_checkpoints TO compliance_auditor;
GRANT SELECT ON backups TO compliance_auditor;

-- Views
GRANT SELECT ON v_compliance_overview TO compliance_auditor;
GRANT SELECT ON v_employee_directory TO compliance_auditor;

-- Compliance Auditor has NO access to raw employee data (PII protection)
-- They access employee details only through v_employee_directory view.
