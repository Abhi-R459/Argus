# Argus — Comprehensive Attack Demo Rehearsal Guide

This guide provides the complete rehearsal protocol for all six attack scenarios demonstrated in the Argus evaluation and viva defense.

---

## Scenario Overview

| Scenario | Attack Description | Layer Tested | Detection / Prevention Mechanism |
|---|---|---|---|
| **Demo 1** | Direct SQL deletion or modification via application role | Database DAC | PostgreSQL `REVOKE UPDATE, DELETE ON audit_log` |
| **Demo 2** | Superuser directly alters historical `audit_log` row | Cryptographic Chain | Standalone verifier detects SHA-256 hash mismatch |
| **Demo 3** | Malicious / erroneous salary decrease > 30% | Business Logic | PostgreSQL `BEFORE INSERT` trigger raises exception |
| **Demo 4** | Employee attempts to modify their own compensation | Access Control | PostgreSQL trigger validates session variable vs. target |
| **Demo 5** | Superuser deletes a checkpoint from `chain_checkpoints` | Checkpoint Layer | Verifier cross-references against external anchor store |
| **Demo 6** | Attacker plants forged checkpoint in external anchor store | External Anchor | Ed25519 asymmetric digital signature verification fails |

---

## Scenario 1: Direct SQL Modification via Application Role

### Objective
Demonstrate that application credentials (`hr_admin` or `compliance_auditor`) cannot tamper with audit logs, even if an attacker extracts the application connection string.

### Execution
Connect as the `hr_admin` role:
```sql
psql -U hr_admin -d argus

-- Attempt to delete historical audit records
DELETE FROM audit_log WHERE sequence_id = 1;
```

### Expected Output
```
ERROR:  permission denied for table audit_log
```

### Validation
`REVOKE UPDATE, DELETE ON audit_log FROM hr_admin, compliance_auditor;` is enforced at the database kernel level, entirely independent of API application code.

---

## Scenario 2: Superuser Direct Tamper Detection

### Objective
Demonstrate that even a database superuser (`postgres`) with complete read/write access cannot silently alter history without cryptographic detection.

### Execution
1. As superuser `postgres`, update an audit log row to alter the logged payload:
   ```sql
   psql -U postgres -d argus

   UPDATE audit_log 
   SET new_value = '{"full_name": "Tampered Employee", "salary": 150000}'::jsonb
   WHERE sequence_id = 5;
   ```
2. Run the standalone verifier CLI from an auditor workstation:
   ```bash
   python -m db.cli.verifier verify-chain
   ```

### Expected Output
```
[ERROR] Hash mismatch at sequence_id=5:
  Stored:     d3b07384d113edec49eaa6238ad5ff00...
  Recomputed: 4f53cda18c2baa0c0354bb5f9a3ecbe5...
Verification Status: FAILED
Total Entries: 25 | Anomalies: 1 (1 hash mismatch, 0 gaps, 0 orphans)
Exit Code: 1
```

---

## Scenario 3: Salary Decrease > 30% Blocked by Trigger

### Objective
Demonstrate that unauthorized, anomalous compensation drops (>30% reduction from latest recorded salary) are rejected atomically at the database tier.

### Execution
```sql
psql -U hr_admin -d argus

-- Current salary is 100,000. Attempt a 40% salary reduction to 60,000:
INSERT INTO salary_history (employee_id, amount, effective_date)
VALUES (1, 60000.00, CURRENT_DATE);
```

### Expected Output
```
ERROR:  Salary decrease cannot exceed 30% of current salary. (Current: 100000.00, Proposed: 60000.00)
CONTEXT:  PL/pgSQL function trg_check_salary_decrease() line 18 at RAISE
```

### Validation
Transaction aborts cleanly. No row is inserted into `salary_history`, and no partial or orphan record enters `audit_log`.

---

## Scenario 4: Self-Salary Modification Blocked by Trigger

### Objective
Prevent insider fraud where an employee who possesses administrative privileges updates their own compensation record.

### Execution
```sql
psql -U hr_admin -d argus

-- Set session context representing Employee ID 10
SET LOCAL argus.actor_user_id = 10;
SET LOCAL argus.actor_employee_id = 10;

-- Employee 10 attempts to give themselves a raise
INSERT INTO salary_history (employee_id, amount, effective_date)
VALUES (10, 150000.00, CURRENT_DATE);
```

### Expected Output
```
ERROR:  Self-salary modification is prohibited. Actor cannot alter their own salary record.
CONTEXT:  PL/pgSQL function trg_salary_history_no_self_mod() line 12 at RAISE
```

---

## Scenario 5: Checkpoint Deletion Detection

### Objective
Demonstrate detection when an adversary deletes intermediate checkpoints inside PostgreSQL to conceal the recompute-and-hide attack.

### Execution
1. Checkpoint row is deleted from the database:
   ```sql
   psql -U postgres -d argus
   DELETE FROM chain_checkpoints WHERE id = 1;
   ```
2. The auditor runs verifier with anchor checking:
   ```bash
   python -m db.cli.verifier verify-chain --check-anchors
   ```

### Expected Output
```
[ERROR] Missing checkpoint in database!
  Anchor store expects checkpoint_id=1 at sequence_id=25.
  Database record does not exist.
Integrity Check: FAILED
Exit Code: 1
```

---

## Scenario 6: Forged Anchor Signature Rejection

### Objective
Demonstrate that an attacker with write access to the external anchor store (e.g. GitHub repo) cannot forge valid checkpoints because they lack the Ed25519 private signing key.

### Execution
1. Attacker places a manually altered or unsigned checkpoint file in the anchor store:
   ```bash
   echo '{"checkpoint_id": 99, "checkpoint_hash": "ffff...", "signature": "0000..."}' > ./anchor/99.json
   ```
2. Auditor runs verifier anchor validation:
   ```bash
   python -m db.cli.verifier verify-chain --verify-anchors
   ```

### Expected Output
```
[SECURITY ALERT] Invalid Ed25519 signature on anchor 99.json!
  Computed Checkpoint Hash: ffff...
  Signature Verification: FAILED (BadSignature)
Integrity Check: FAILED
Exit Code: 1
```
