-- Argus PostgreSQL Role Setup & Permissions Initialization Script (DB-006)
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

-- 2. Skeleton GRANTs for HR Admin
GRANT CONNECT ON DATABASE argus TO hr_admin;
GRANT USAGE ON SCHEMA public TO hr_admin;
GRANT SELECT, INSERT, UPDATE ON departments TO hr_admin;
GRANT SELECT, INSERT, UPDATE ON roles TO hr_admin;
GRANT SELECT, INSERT, UPDATE ON users TO hr_admin;
GRANT SELECT, INSERT, UPDATE ON employees TO hr_admin;
GRANT SELECT, INSERT, UPDATE ON salary_history TO hr_admin;
GRANT SELECT ON v_employee_directory TO hr_admin;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO hr_admin;

-- 3. Skeleton GRANTs for Compliance Auditor
GRANT CONNECT ON DATABASE argus TO compliance_auditor;
GRANT USAGE ON SCHEMA public TO compliance_auditor;
GRANT SELECT ON audit_log TO compliance_auditor;
GRANT SELECT ON suspicious_activity_flags TO compliance_auditor;
GRANT SELECT ON chain_state TO compliance_auditor;
GRANT SELECT ON chain_checkpoints TO compliance_auditor;
GRANT SELECT ON backups TO compliance_auditor;
GRANT SELECT ON v_compliance_overview TO compliance_auditor;
