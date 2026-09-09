# Attack Demo #2 — Superuser Direct Tamper Detection

**Task:** DB-011  
**Scenario:** A PostgreSQL superuser directly modifies a historical `audit_log` row using `psql`, bypassing all application-layer access controls.

---

## Threat Model

- **Attacker:** A compromised or rogue DBA with `postgres` superuser privileges.
- **Action:** Directly `UPDATE`s an `audit_log` row to change its `old_value` or `new_value` JSONB — for example, to hide a fraudulent salary change.
- **Goal:** Silently alter the historical record without detection.

---

## Why the Attack Succeeds at the DB Level

PostgreSQL superusers bypass:
- Row-Level Security (RLS) policies
- `REVOKE` statements on tables
- Application-layer authentication (Clerk JWT)

The superuser can directly execute:

```sql
-- Attacker connects as postgres
psql -U postgres -d argus

-- Silently modify a historical audit_log row
UPDATE audit_log
SET    new_value = '{"full_name": "Hacked Employee", "email": "hack@evil.com", "role_id": 99}'::JSONB
WHERE  sequence_id = 5;
```

---

## Why the Attack is DETECTED by Argus

The hash chain detects the tamper because:

1. Each `audit_log` row's `entry_hash` was computed at write-time as:
   ```
   SHA-256(serialized_payload || previous_hash)
   ```
2. The attacker's `UPDATE` changes `new_value` but **cannot** recompute a valid `entry_hash` without
   breaking `entry_hash[n+1].previous_hash = entry_hash[n]`.
3. Any attempt to also update `entry_hash` breaks the chain at `sequence_id = n+1`, where
   `previous_hash` no longer matches the modified row.
4. The standalone verifier (`verify-chain`) recomputes every hash independently and reports any mismatch.

---

## Attack Simulation Steps

### Setup: Insert legitimate data

```sql
-- As API (argus app user): set session context
SET LOCAL argus.actor_user_id = 1;
SET LOCAL argus.actor_employee_id = 0;

-- Insert a test employee (triggers audit_log entry)
INSERT INTO employees (full_name, email, role_id, national_id_encrypted, contact_info_encrypted, date_hired)
VALUES ('Alice Smith', 'alice@argus.com', 1, '\xDEADBEEF'::BYTEA, '\xCAFEBABE'::BYTEA, '2025-01-01');

-- Record the sequence_id of the audit entry
SELECT sequence_id, entry_hash, previous_hash, new_value
FROM   audit_log
ORDER  BY sequence_id DESC
LIMIT  3;
```

### Attack: Superuser modifies the audit row

```sql
-- As postgres superuser
\c argus postgres

UPDATE audit_log
SET    new_value = '{"tampered": true}'::JSONB
WHERE  sequence_id = 1;

-- Verify the row was changed (no error — superuser bypasses REVOKE)
SELECT sequence_id, new_value FROM audit_log WHERE sequence_id = 1;
```

### Detection: Run the verifier

```bash
# Standalone verifier (to be implemented in VERIFY-001 through VERIFY-003)
python db/cli/verifier.py verify-chain --db-url $DATABASE_URL
```

**Expected Output:**
```
[ERROR] Hash mismatch at sequence_id=1:
  Stored:     a3f2c1d4e5b6...  (original hash)
  Recomputed: 9f1e7a2b3c0d...  (hash of tampered row)
Chain integrity FAILED. 1 anomaly detected.
Exit code: 1
```

---

## Expected Outcomes

| Step | Outcome |
|------|---------|
| Superuser `UPDATE` on `audit_log` | **Succeeds** — superuser bypasses `REVOKE` |
| Hash chain verification | **Detects tamper** — recomputed hash ≠ stored hash |
| Exit code | `1` (anomaly detected) |

---

## Mitigation

Argus's tamper-evidence guarantee does NOT prevent the superuser from modifying data — it **detects** it. The `compliance_auditor` role must run `verify-chain` regularly (or on-demand) to surface tampering. For complete prevention, consider:

1. PostgreSQL audit extensions (e.g., `pgaudit`) to log superuser activity.
2. External WAL-based replication for a read-only audit replica.
3. Regular signed checkpoints anchored externally (CRYPTO-002 through CRYPTO-005).
