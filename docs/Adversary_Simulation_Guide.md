# Argus Adversary Simulation Engine — Evaluator Demonstration Manual (DOC-009)

> **Document Version:** 1.0  
> **Date:** September 12, 2026  
> **Applicable Branch:** `feature/abhinav-core`  
> **Engine Module:** [`db/cli/adversary.py`](../db/cli/adversary.py)  
> **Threat Model Mapping:** Section 16.2 Adversary Taxonomy ($A_{DBA}, A_{APP}$)

---

## 1. Executive Summary & Architectural Rationale

In real-world enterprise deployments, **no internal backdoor, attack simulation endpoint, or chaos testing harness belongs inside the production web application**. 

A genuine rogue administrator ($A_{DBA}$) or compromised service account does not access the web user interface to alter records; they connect directly to the relational database using privileged native tooling (`psql`, raw TCP sockets, pgAdmin) to mutate records behind the back of the application layer.

Argus models this reality with strict architectural segregation:
1. **Zero Production Backdoors:** The FastAPI backend and Vite frontend contain **zero intentional flaws, bypass routes, or attack fixtures**. All route handlers enforce fail-closed cryptographic verification.
2. **Out-of-Band Administrative Engine:** Adversarial simulation is implemented as a standalone, administrative Red Team CLI (`db.cli.adversary`).
3. **Deterministic Snapshot & Healing:** Every simulated attack automatically captures an atomic pre-tampered snapshot (`.argus_snapshot.json`) with sub-millisecond precision, enabling one-command deterministic restoration back to 100% cryptographic validity.

```
┌─────────────────────────────────────────────────────────┐
│               Enterprise Browser Client                 │
│      React Dashboard (http://localhost:5173/auditor)    │
└───────────────────────────┬─────────────────────────────┘
                            │ HTTPS / REST (Fail-Closed)
                            ▼
┌─────────────────────────────────────────────────────────┐
│               Argus Core Web API                        │
│          (FastAPI - Port 8000, Zero Backdoors)          │
└───────────────────────────┬─────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────┐     Out-of-Band Superuser SQL
│               PostgreSQL Database Engine                │ ◄────────────────────────────────┐
│   - audit_log (SHA-256 linear hash chain)               │                                  │
│   - chain_state (atomic tail mutex)                     │                     ┌────────────┴───────────┐
│   - chain_checkpoints (Ed25519 signed commitments)      │                     │ Argus Adversary Engine │
└───────────────────────────┬─────────────────────────────┘                     │  (db/cli/adversary.py) │
                            │                                                   │  Direct Rogue DBA CLI  │
                            ▼                                                   └────────────────────────┘
┌─────────────────────────────────────────────────────────┐
│         External Immutable Anchor Store                 │
│      (Local filesystem / GitHub repository commits)     │
└─────────────────────────────────────────────────────────┘
```

---

## 2. Live Demonstration Walkthrough (Side-by-Side)

This rehearsal script is designed for live evaluators, thesis defense committees, and technical auditors. 
For optimal demonstration effect, position the **Enterprise Auditor Dashboard** on one half of the screen and an **Administrative Terminal** on the other half.

### Pre-Requisite Verification: Baseline System Health
1. Open the Auditor Dashboard:
   ```
   http://localhost:5173/auditor/overview
   ```
2. In your terminal, check system status:
   ```powershell
   python -m db.cli.adversary status
   ```
   **Expected Terminal Output:**
   ```text
   +-------------------------------------------------------------------+
   |                   ARGUS ADVERSARY ENGINE                          |
   |        Out-of-Band Red Team Database Attack Simulation            |
   +-------------------------------------------------------------------+

   [*] Diagnosing Database and Verifier Integrity...

   [OK] System Normal (No active adversary attacks staged).

     Total Audit Log Entries : 49
     Total Checkpoints       : 2
     Internal Hash Chain     : VALID (INTACT)
     External Anchor Store   : MATCH (Anchor 2 matches external store.)
   ```
3. In the browser dashboard, click **"Verify Chain"**.
   - The status badge displays **`VALID (Green)`**.
   - The verified chain visualizer displays uninterrupted green continuity nodes.

---

### Demonstration 1: Rogue DBA Historical Salary Tampering (`dba-row-tamper`)

**Attack Hypothesis:** A rogue DBA connects with superuser privileges directly to PostgreSQL and modifies an employee's historical salary record in `audit_log` without updating the cryptographic hash chain.

1. **Inject Attack:**
   ```powershell
   python -m db.cli.adversary attack --scenario dba-row-tamper --sequence-id 29
   ```
   **Console Output:**
   ```text
   [+] Attack Injected Successfully!
       Target Sequence ID : 29
       SQL Executed       : UPDATE audit_log SET new_value = '{"_unauthorized_dba_bonus": 250000.0, "tampered_by": "rogue_dba_sql_mutation", "amount": 999999.0}' WHERE sequence_id = 29;
   ```

2. **Observe in Dashboard:**
   - In the Auditor Dashboard, click **"Verify Chain"**.
   - **Result:** The system status immediately flips to **`TAMPERED (Red)`**.
   - **Violation Banner:** `Hash mismatch at sequence_id 29: expected 8f74fff8abea2c69... actual 29bfe07c6c567da8...`
   - The chain visualizer highlights node 29 in glowing red, indicating the exact record where the database was violated.

3. **Deterministic Healing:**
   ```powershell
   python -m db.cli.adversary heal
   ```
   **Console Output:**
   ```text
   [*] Restoring database integrity from snapshot...
   [OK] HEAL SUCCESSFUL!
       Reverted Scenario  : dba-row-tamper
       Entries Verified   : 49
       Chain Status       : 100% VALID (Zero Tampering)
   ```
   - Re-click **"Verify Chain"** in the browser dashboard. The chain instantly recovers to **`VALID (Green)`**.

---

### Demonstration 2: Sophisticated Forward Hash Recalculation (`recompute-and-hide`)

**Attack Hypothesis:** A sophisticated adversary knows that altering a row causes a hash mismatch. They alter a historical row and **recalculate all forward SHA-256 chain hashes up to the current tail**, updating `audit_log` and `chain_state`.

*Question for Evaluators:* Can a database-only ledger catch this attack?  
*Answer:* **No.** Any database-only ledger (such as naive audit tables or un-anchored chains) will be completely fooled because the internal math appears self-consistent. **Argus catches this because of its external asymmetric anchor tier.**

1. **Inject Attack:**
   ```powershell
   python -m db.cli.adversary attack --scenario recompute-and-hide --sequence-id 20
   ```
   **Console Output:**
   ```text
   [+] Recompute Attack Injected Successfully!
       Target Sequence ID : 20
       Forward Rows Fixed : 30
       New Tail Hash      : 4b29f0e1a89c7d12...
   ```

2. **Verify Internal vs. External Evidence:**
   ```powershell
   python -m db.cli.adversary status
   ```
   **Console Output:**
   ```text
     Internal Hash Chain     : VALID (INTACT)
     External Anchor Store   : MISMATCH (Anchor mismatch for checkpoint 2: DB hash 4b29... != Anchor 1fb6...)
   ```
   - **Key Finding:** The internal sequential hash chain passed, but the **external Ed25519 anchor store caught the unauthorized forgery**.
   - Because the attacker does not possess the auditor's Ed25519 private key (`verifier_private_key.pem`), they could not generate a valid signature for the forged checkpoint in the immutable anchor store.

3. **Deterministic Healing:**
   ```powershell
   python -m db.cli.adversary heal
   ```
   - Database, tail hashes, and checkpoints return to 100% agreement with the external anchor.

---

### Demonstration 3: Checkpoint Signature Corruption (`checkpoint-forgery`)

**Attack Hypothesis:** An attacker attempts to forge or manipulate an existing checkpoint signature inside `chain_checkpoints`.

1. **Inject Attack:**
   ```powershell
   python -m db.cli.adversary attack --scenario checkpoint-forgery
   ```

2. **Observe Failure:**
   - The verifier validates the checkpoint hash against the auditor's Ed25519 public key.
   - The signature check fails immediately with cryptographic rejection (`INVALID_SIGNATURE`).

3. **Deterministic Healing:**
   ```powershell
   python -m db.cli.adversary heal
   ```

---

### Demonstration 4: Physical Row Deletion & Gap Detection (`delete-audit-row`)

**Attack Hypothesis:** An adversary executes `DELETE FROM audit_log WHERE sequence_id = 25;` to purge evidence of an unauthorized transaction.

1. **Inject Attack:**
   ```powershell
   python -m db.cli.adversary attack --scenario delete-audit-row --sequence-id 25
   ```

2. **Observe in Dashboard:**
   - In the Auditor Dashboard, click **"Verify Chain"**.
   - **Result:** Status immediately flips to **`TAMPERED`**.
   - **Violation Details:** `Sequence gap detected at sequence_id 25: expected 25, found 26.`
   - The verifier detects that an entry was unlawfully expunged from the append-only ledger.

3. **Deterministic Healing:**
   ```powershell
   python -m db.cli.adversary heal
   ```
   - Row 25 is re-inserted with its exact historical payload, cryptographic hash, and timestamp. The chain is validated 100% intact.

---

## 3. Command-Line Reference

| Command | Arguments | Purpose |
| :--- | :--- | :--- |
| `attack` | `--scenario dba-row-tamper [--sequence-id N]` | Mutates historical audit row without updating hash. |
| `attack` | `--scenario recompute-and-hide [--sequence-id N]` | Mutates row and rewrites all forward hashes to test anchor detection. |
| `attack` | `--scenario checkpoint-forgery [--checkpoint-id N]` | Corrupts Ed25519 signature in database checkpoint table. |
| `attack` | `--scenario delete-audit-row [--sequence-id N]` | Deletes historical audit log record to trigger gap detection. |
| `heal` | `[--snapshot-path PATH]` | Reverts all mutations and restores database to 100% valid state. |
| `status` | `[--snapshot-path PATH]` | Inspects active attack state, chain continuity, and anchor alignment. |

---

## 4. Academic & Security Comparison Matrix

| Attack Scenario | Naive Audit Table | CloudTrails / S3 | Argus (3-Tier Engine) |
| :--- | :---: | :---: | :---: |
| **Direct DBA UPDATE** | ❌ Undetected | ❌ Undetected on DB | ✅ **Immediate Hash Mismatch** |
| **Direct DBA DELETE** | ❌ Undetected | ❌ Undetected on DB | ✅ **Sequence Gap Detected** |
| **Forward Hash Rewriting** | ❌ Undetected | ❌ Undetected | ✅ **Anchor Store Mismatch** |
| **Checkpoint Forgery** | ❌ Not Supported | ❌ Vendor Key Only | ✅ **Ed25519 Rejection** |
| **Fail-Closed API Verifier** | ❌ Fail-Open | N/A | ✅ **Fail-Closed on Drop** |
