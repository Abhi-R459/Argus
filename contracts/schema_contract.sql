-- Database Schema Contract - Frozen after Week 1
-- This contract outlines the SQL structure that both developers agree on.
-- All migrations and ORM models must conform to this schema.

-- 1. Departments Table
CREATE TABLE departments (
    department_id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL UNIQUE
);

-- 2. Roles Table (Employee Job Titles)
CREATE TABLE roles (
    role_id SERIAL PRIMARY KEY,
    title VARCHAR(255) NOT NULL,
    department_id INT NOT NULL REFERENCES departments(department_id),
    salary_band_min NUMERIC(12, 2) NOT NULL,
    salary_band_max NUMERIC(12, 2) NOT NULL,
    CONSTRAINT chk_salary_band CHECK (salary_band_min <= salary_band_max)
);

-- 3. Users Table (Application Users for RBAC / Clerk integration)
CREATE TABLE users (
    user_id SERIAL PRIMARY KEY,
    clerk_user_id VARCHAR(255) NOT NULL UNIQUE,
    full_name VARCHAR(255) NOT NULL,
    email VARCHAR(255) NOT NULL UNIQUE,
    role VARCHAR(50) NOT NULL CHECK (role IN ('hr_admin', 'compliance_auditor')),
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- 4. Employees Table
CREATE TABLE employees (
    employee_id SERIAL PRIMARY KEY,
    full_name VARCHAR(255) NOT NULL,
    email VARCHAR(255) NOT NULL UNIQUE,
    role_id INT NOT NULL REFERENCES roles(role_id),
    national_id_encrypted BYTEA NOT NULL, -- Encrypted using pgcrypto
    contact_info_encrypted BYTEA NOT NULL, -- Encrypted using pgcrypto
    date_hired DATE NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- 5. Salary History Table
CREATE TABLE salary_history (
    salary_history_id SERIAL PRIMARY KEY,
    employee_id INT NOT NULL REFERENCES employees(employee_id),
    amount NUMERIC(12, 2) NOT NULL CHECK (amount > 0),
    effective_date DATE NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_employee_salary_date UNIQUE (employee_id, effective_date)
);

-- 6. Audit Log Table (Hash Chain)
CREATE TABLE audit_log (
    sequence_id BIGINT PRIMARY KEY, -- Monotonically increasing ID managed by trigger / chain state
    actor_user_id INT NOT NULL REFERENCES users(user_id),
    employee_id INT REFERENCES employees(employee_id), -- Nullable, tracks target employee
    action VARCHAR(20) NOT NULL CHECK (action IN ('INSERT', 'UPDATE', 'DELETE')),
    table_name VARCHAR(100) NOT NULL,
    row_id INT NOT NULL,
    old_value JSONB, -- Masked / redacted for sensitive columns
    new_value JSONB, -- Masked / redacted for sensitive columns
    severity VARCHAR(20) NOT NULL CHECK (severity IN ('INFO', 'WARNING', 'CRITICAL')),
    entry_hash CHAR(64) NOT NULL, -- SHA-256 hash of payload + previous_hash
    previous_hash CHAR(64) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- 7. Suspicious Activity Flags Table
CREATE TABLE suspicious_activity_flags (
    flag_id SERIAL PRIMARY KEY,
    audit_log_sequence_id BIGINT NOT NULL REFERENCES audit_log(sequence_id),
    reviewed_by_user_id INT REFERENCES users(user_id),
    reviewed_at TIMESTAMPTZ,
    flag_reason VARCHAR(255) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- 8. Chain State Table (Singleton tracking current tail)
CREATE TABLE chain_state (
    id INT PRIMARY KEY CHECK (id = 1),
    tail_hash CHAR(64) NOT NULL,
    tail_sequence_id BIGINT NOT NULL,
    last_checkpoint_sequence_id BIGINT NOT NULL
);

-- 9. Chain Checkpoints Table (Signed checkpoints)
CREATE TABLE chain_checkpoints (
    checkpoint_id SERIAL PRIMARY KEY,
    sequence_id BIGINT NOT NULL REFERENCES audit_log(sequence_id),
    checkpoint_hash CHAR(64) NOT NULL,
    signature BYTEA NOT NULL, -- Asymmetric signature (Ed25519)
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- 10. Backups Table (Tracks native database backups)
CREATE TABLE backups (
    backup_id SERIAL PRIMARY KEY,
    chain_checkpoint_id INT REFERENCES chain_checkpoints(checkpoint_id),
    backup_hash CHAR(64) NOT NULL,
    file_reference VARCHAR(255) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Indices for Verification and Optimization
CREATE INDEX idx_audit_log_seq_time ON audit_log (sequence_id, created_at);
CREATE INDEX idx_audit_log_employee_time ON audit_log (employee_id, created_at);
