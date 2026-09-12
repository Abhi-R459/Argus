# Argus Enterprise Feature Guide & Live Demonstration Manual
**Cryptographically Verifiable, Tamper-Evident Relational Database System**  
*Academic viva presentation guide, operational runbook, and regulatory compliance blueprint.*

---

## Executive Summary & System Overview

Argus is an enterprise-grade, cryptographically verifiable database architecture built on PostgreSQL 15, FastAPI, and React. Traditional relational database audit logs suffer from a fundamental vulnerability: **the Database Administrator ($A_{DBA}$) or an attacker with raw SQL credentials can silently mutate, insert, or delete audit records without leaving an operational trace**.

Argus solves this by turning standard PostgreSQL relational tables into a **mathematically verifiable, append-only cryptographic hash chain**, reinforced with:
1. **Asymmetric Ed25519 Checkpoint Signatures:** Digital certificates establishing non-repudiation.
2. **External Anchor Stores:** Git/file-backed out-of-band trust roots that prevent forward hash recalculation attacks.
3. **Two-Layer Role-Based Access Control (RBAC):** Dual connection pool database isolation ensuring true least privilege.
4. **HMAC-SHA256 Blind Indexing:** Zero-knowledge search capabilities over AES-256 encrypted Personally Identifiable Information (PII).
5. **Point-in-Time State Reconstruction (Time-Travel):** Delta-driven state playback across historical timestamps.
6. **Automated Risk & Fraud Detection:** Database-level heuristics detecting salary spikes and mass data exfiltration/deletion.
7. **Offline Evidence Bundles (`.arguspack`):** Self-contained, cryptographically signed audit archives verifiable by external regulators without database credentials.

---

## Quick Navigation Table of Features

| # | Feature | Subsystem | Target Persona | Primary Security / Compliance Objective |
|---|---|---|---|---|
| 1 | [Cryptographic Hash-Chained Audit Trail](#1-cryptographic-hash-chained-audit-trail) | PostgreSQL Engine & Triggers | System / All | Tamper evidence, forward integrity ($O(1)$ write) |
| 2 | [Two-Layer RBAC & Dual-Pool Isolation](#2-two-layer-rbac--dual-pool-connection-isolation) | FastAPI & PostgreSQL Roles | HR Admin vs Auditor | Principle of least privilege, zero-trust database |
| 3 | [Database-Level Business Integrity Triggers](#3-database-level-business-integrity-triggers) | PL/pgSQL BEFORE Triggers | HR Admin / All | Fraud prevention, self-dealing block, data sanity |
| 4 | [Asymmetric Checkpointing & External Anchoring](#4-asymmetric-checkpointing--external-anchoring) | Python CLI & Anchor Store | Compliance Auditor | Non-repudiation, prevents $A_{DBA}$ forward hash rewrites |
| 5 | [AES-256 Encryption & HMAC Blind Search](#5-aes-256-encryption--hmac-sha256-blind-indexing) | `pgcrypto` & API Service | HR Admin / Auditor | Data privacy at rest, searchable encrypted PII (GDPR) |
| 6 | [HR Admin Portal & Employee Management](#6-hr-admin-portal--employee-lifecycle-management) | React Frontend (`/admin`) | HR Administrator | Segregated operations without audit tampering access |
| 7 | [Global Incident State & Persistent Alerting](#7-global-incident-state--persistent-alerting) | React Frontend (`AuditorLayout`) | Compliance Auditor | Real-time visibility of out-of-band database breaches |
| 8 | [Interactive Full-Page Chain Explorer](#8-interactive-full-page-chain-explorer) | React Frontend (`/auditor/chain`) | Compliance Auditor | Block inspection, hash verification, JSON property diffs |
| 9 | [Auditor Audit Log Table & Deep Scrubbing](#9-auditor-audit-log-table--deep-forensic-scrubbing) | React Frontend (`/auditor/log`) | Compliance Auditor | Keyset pagination, actor attribution, blind index lookup |
| 10 | [Historical Time-Travel State Reconstruction](#10-historical-time-travel-state-reconstruction) | PL/pgSQL & React (`/auditor/time-travel`) | Compliance Auditor | Point-in-time state rollback & forensic timeline |
| 11 | [Automated Risk & Fraud Detection Engine](#11-automated-risk--fraud-detection-engine) | PL/pgSQL Procedure & UI (`/auditor/risk`) | Compliance Auditor | Automated anomaly detection, SOX fraud alerts |
| 12 | [Self-Contained Evidence Pack Export](#12-self-contained-cryptographic-evidence-pack-export) | Export Service (`.arguspack`) | External Regulators | Third-party independent verification without DB access |
| 13 | [High-Throughput Concurrency Lab](#13-high-throughput-concurrency-lab) | FastAPI & React (`/auditor/concurrency`) | Evaluators / QA | Proof of Two-Phase Locking (2PL) write serialization |
| 14 | [Out-of-Band Adversary Simulation CLI](#14-out-of-band-adversary-simulation-cli) | Standalone CLI (`db/cli/adversary.py`) | Red Team / Evaluator | Live demonstration of rogue DBA attacks and healing |

---

## 1. Cryptographic Hash-Chained Audit Trail

### What It Is For
In standard databases, audit logs are plain tables where records can be silently edited (`UPDATE audit_log SET ...`) or deleted. Argus implements a **linear cryptographic hash chain** where every mutation (INSERT, UPDATE, DELETE) automatically calculates a SHA-256 digest linked to the previous entry:
$$H_i = \text{SHA256}(H_{i-1} \,\|\, S(R_i))$$
where $H_{i-1}$ is the hash of the immediately preceding audit record, and $S(R_i)$ is the deterministic canonical JSON serialization of the event payload. 

### How to Use It
The hash chain operates **entirely autonomously** inside PostgreSQL. Whenever an HR Administrator inserts an employee, edits a department, or updates a compensation figure:
1. An `AFTER INSERT OR UPDATE OR DELETE` trigger fires.
2. The trigger acquires an exclusive row lock on `chain_state` using `SELECT current_hash, current_sequence_id FROM chain_state FOR UPDATE`.
3. It increments the sequence ID, constructs the canonical payload string, computes the SHA-256 digest, writes the audit row, and advances `chain_state`.

### Real-World Benefit & Regulatory Compliance
- **SOC 2 Type II (Common Criteria 6.8 & 7.2):** Guarantees complete audit trail immutability and continuous tracking of changes.
- **SOX Section 404:** Ensures that financial records, employee compensation, and corporate ledger histories cannot be manipulated by accounting or IT personnel.
- **Zero Overhead on Read Operations:** Verifications and queries read without blocking concurrent writes.

### How to Explain and Demonstrate It (Viva & Presentation)
- **Explanation Script:**
  > *"Examiners, standard audit tables are vulnerable to anyone with root database credentials. In Argus, every database mutation passes through an AFTER trigger that enforces mathematical chain continuity. Modifying even a single character in an old row alters its SHA-256 hash, immediately breaking the link to all subsequent records. Concurrency is strictly serialized using Two-Phase Locking (2PL) on a dedicated `chain_state` row, preventing hash chain forks without locking the business tables."*
- **Live Demo Steps:**
  1. Open the PostgreSQL terminal or web browser.
  2. Perform an employee update in the HR portal.
  3. Navigate to `http://localhost:5173/auditor/chain`.
  4. Point out that a new block has been appended at the top with a distinct `sequence_id`, `entry_hash`, and a `previous_hash` identical to the preceding block's hash.

---

## 2. Two-Layer RBAC & Dual-Pool Connection Isolation

### What It Is For
Web applications frequently commit the architectural error of using a single database superuser connection pool (`postgres`) for all queries, relying solely on application-level `if (user.role == 'admin')` statements. If an application bug, injection flaw, or malicious package is introduced, an attacker inherits full database privileges.

Argus enforces **True Two-Layer Defense-in-Depth**:
- **Layer 1 (Application):** Clerk JWT authentication and FastAPI role dependencies (`require_role(["compliance_auditor"])`).
- **Layer 2 (Database):** Two segregated PostgreSQL connection pools:
  - `DATABASE_URL_HR_ADMIN`: Connects as PostgreSQL role `hr_admin`. Has CRUD on entity tables, but **strictly revoked `UPDATE` and `DELETE` on `audit_log`**.
  - `DATABASE_URL_COMPLIANCE_AUDITOR`: Connects as PostgreSQL role `compliance_auditor`. Has **read-only access to audit tables**, but **zero SELECT privileges on raw `employees` tables** (protecting employee PII).

### How to Use It
1. When logging in as an HR Administrator, the FastAPI router dynamically selects the `_hr_admin_engine` pool.
2. When logging in as a Compliance Auditor, requests route to `_compliance_auditor_engine`.
3. The routing happens transparently in `api/dependencies.py` via `get_db_session`.

### Real-World Benefit & Regulatory Compliance
- **Principle of Least Privilege (PoLP):** Eliminates privilege escalation vulnerabilities.
- **HIPAA Privacy Rule & GDPR Article 25 (Privacy by Design):** Auditors evaluating system integrity cannot browse confidential employee personnel records (salaries, medical contacts, national IDs).
- **Insider Threat Defense:** An HR admin cannot cover their tracks by executing raw SQL against the audit log, because `REVOKE UPDATE, DELETE ON audit_log FROM hr_admin` is enforced at the database engine kernel level.

### How to Explain and Demonstrate It (Viva & Presentation)
- **Explanation Script:**
  > *"Notice that we do not trust application code alone to restrict access. We implement dual database connection pools. An HR Admin cannot alter the audit log even with a SQL injection exploit, because PostgreSQL itself rejects the command. Conversely, an Auditor can inspect cryptographic hashes and directory overviews, but PostgreSQL blocks them from reading raw sensitive employee tables."*
- **Live Demo Steps:**
  1. Open PowerShell and run:
     ```powershell
     docker exec -i argus-postgres psql -U compliance_auditor -d argus -c "SELECT * FROM employees;"
     ```
  2. Show the audience the instant engine rejection:
     `ERROR: permission denied for table employees`
  3. Next run:
     ```powershell
     docker exec -i argus-postgres psql -U hr_admin -d argus -c "DELETE FROM audit_log WHERE sequence_id = 1;"
     ```
  4. Show the engine rejection:
     `ERROR: permission denied for table audit_log`

---

## 3. Database-Level Business Integrity Triggers

### What It Is For
Certain compliance and fraud rules must be enforced unconditionally, regardless of whether a query originates from the official API, a third-party microservice, or an accidental manual database query by an administrator.

Argus embeds core business logic directly into **PostgreSQL `BEFORE` triggers**:
1. **Self-Salary Modification Block (`trg_salary_history_self_block_fn`):** An administrator cannot insert or update a salary history record where the employee corresponds to their own user identity.
2. **Excessive Salary Decrease Guard (`trg_salary_history_decrease_check_fn`):** Rejects any single salary reduction exceeding 30%, preventing spiteful wage slashing or catastrophic data entry typos.
3. **Immutable Identity Guard (`trg_employees_national_id_immutable_fn`):** Prevents modification of an employee's National ID once registered.

### How to Use It
- Simply attempt to perform an unauthorized modification. The PostgreSQL trigger will intercept the transaction and raise a `RAISE EXCEPTION` before any disk write occurs, causing FastAPI to return an informative HTTP 400 or 403 error.

### Real-World Benefit & Regulatory Compliance
- **Fraud & Embezzlement Mitigation:** Prevents rogue HR personnel from granting themselves pay raises.
- **Data Quality & Mistake Proofing (Poka-Yoke):** Prevents fat-finger errors during payroll adjustments.

### How to Explain and Demonstrate It (Viva & Presentation)
- **Live Demo Command:**
  ```powershell
  docker exec -i argus-postgres psql -U postgres -d argus -c "
  DO \$\$
  BEGIN
    SET LOCAL argus.actor_user_id = '1';
    INSERT INTO salary_history (employee_id, amount, effective_date)
    VALUES (1, 999999, CURRENT_DATE);
  END \$\$;"
  ```
- **Expected Console Output:**
  ```text
  ERROR: Unauthorized: An actor cannot insert or modify their own salary history.
  ```

---

## 4. Asymmetric Checkpointing & External Anchoring

### What It Is For
If an attacker gains PostgreSQL superuser access ($A_{DBA}$), they could theoretically alter an old audit entry and write a script to recompute all forward SHA-256 hashes ($H_{i+1}, H_{i+2}, \dots$). A purely local hash chain cannot defend against this forward-recalculation attack.

Argus neutralizes this through **Asymmetric Ed25519 Checkpointing and External Anchoring**:
1. Every $k=25$ entries, the system computes a cumulative checkpoint root hash.
2. The standalone verifier signs this checkpoint hash using a secure, offline **Ed25519 private key** (`keys/verifier_private_key.pem`).
3. The signed checkpoint is published to an **external, out-of-band anchor store** (`anchor/chain_anchor.log` or remote GitHub repository).
4. If a rogue DBA mutates a row and recalculates all internal database hashes, the recalculated tail hash will fail to match the signed external anchor store!

### How to Use It
- **Run Verification in UI:** Navigate to `http://localhost:5173/auditor/overview` and click **"Run Verification"**.
- **Run Standalone Verifier in Terminal:**
  ```powershell
  .\.venv\Scripts\python.exe -m db.cli.verify_standalone
  ```

### Real-World Benefit & Regulatory Compliance
- **Non-Repudiation (ISO 27001 & FIPS 186-5):** Ed25519 asymmetric cryptography provides mathematical proof of authenticity that cannot be forged even by the database administrator.
- **Out-of-Band Integrity:** Satisfies strict regulatory requirements for off-site tamper-proof log archival.

### How to Explain and Demonstrate It (Viva & Presentation)
- **Explanation Script:**
  > *"If a malicious DBA has root access, why can't they just alter a salary and rewrite all subsequent hashes? In Argus, they can rewrite the database, but they cannot rewrite the external anchor store. Our standalone verifier periodically takes the root hash, signs it with an offline Ed25519 private key, and commits it outside the database. Any discrepancy between database state and external anchor raises an immediate alert."*

---

## 5. AES-256 Encryption & HMAC-SHA256 Blind Indexing

### What It Is For
Regulations like GDPR, HIPAA, and CCPA require sensitive personal data (National IDs, SSNs, medical phone numbers) to be encrypted at rest. However, standard AES-256 encryption generates different ciphertexts each time (due to random IVs), making SQL queries like `WHERE national_id = '...'` impossible without decrypting the entire table into memory (an $O(N)$ CPU disaster).

Argus implements **HMAC-SHA256 Blind Indexing**:
1. The plaintext National ID is encrypted using AES-256 (`pgp_sym_encrypt` in `pgcrypto`) and stored in `national_id_encrypted`.
2. Simultaneously, a deterministic keyed hash is calculated using HMAC-SHA256 with an isolated audit salt:
   $$\text{BlindIndex} = \text{HMAC-SHA256}(K_{\text{salt}}, \text{Plaintext})$$
3. The blind index is stored in the database and audit logs, allowing $O(1)$ exact-match lookups without ever decrypting sensitive data or exposing plaintext.

### How to Use It
1. In the Auditor Portal, navigate to **Audit Log** (`http://localhost:5173/auditor/log`).
2. Enter a National ID in the **"National ID Search (Blind Index)"** field.
3. The API hashes the query with `AUDIT_SALT` and retrieves matching historical records with zero plaintext decryption overhead.

### Real-World Benefit & Regulatory Compliance
- **GDPR Article 17 ("Right to be Forgotten") & Article 32 ("Security of Processing"):** Encrypts confidential data while maintaining verifiable audit records.
- **Protection Against Memory Dumps & Disk Theft:** Even if raw database files (`.mdf`/`.ibd`/PostgreSQL data clusters) are stolen, sensitive employee credentials remain encrypted with AES-256.

---

## 6. HR Admin Portal & Employee Lifecycle Management

### What It Is For
Provides operational personnel with an intuitive, clean interface for everyday employee lifecycle workflows (onboarding, compensation changes, department assignments) while remaining strictly sandboxed within the `hr_admin` least-privilege boundary.

### How to Use It
1. Open **[http://localhost:5173/admin/employees](http://localhost:5173/admin/employees)**.
2. **Search & Filter:** Search employees by name, filter by department (Engineering, Sales, etc.), or filter by status.
3. **Onboard Employee:** Click **"Add Employee"**, fill in name, email, department, role, salary, and national ID. Click **"Submit"**.
4. **Edit Salary:** Click **"Edit Salary"** on any employee card, enter the new compensation and effective date, and submit.
5. Notice that every action instantly generates a cryptographically signed audit block in the background.

---

## 7. Global Incident State & Persistent Alerting

### What It Is For
In traditional monitoring consoles, an alert is only visible if the auditor happens to be looking at a specific "Alerts" page. If an attacker attacks the database while the auditor is inspecting a historical log or looking at an employee, the alert goes unnoticed.

Argus solves this with a **Global Reactive Incident State**:
- The `useIncidentStatus()` hook synthesizes real-time data from verifier health checks, external anchor status, and unreviewed security flags.
- If tampering or an anchor mismatch is detected anywhere in the system, a **persistent, high-contrast crimson banner** appears across the top of **all auditor pages**.
- The banner includes a direct deep-link CTA: `"Inspect Compromised Block #X →"`.
- The sidebar dynamically updates with a pulsating red status indicator and numerical alert badges.

### How to Use It
- The alert banner activates automatically whenever tampering is detected by the verifier or when an adversary attack is simulated.
- Clicking the banner button immediately transports the auditor to the exact affected block in the Chain Explorer.

---

## 8. Interactive Full-Page Chain Explorer

### What It Is For
Provides an enterprise forensic workbench for deep cryptographic chain inspection. Auditors can inspect individual blocks, verify parent-child SHA-256 linkages, check Ed25519 checkpoint associations, and view property-level before/after JSON diffs.

### How to Use It
1. Navigate to **[http://localhost:5173/auditor/chain](http://localhost:5173/auditor/chain)**.
2. **Header Metrics:** View total blocks, current tail hash, and active checkpoint count.
3. **Keyset Windowing:** Use the pagination controls or specify `?around_seq=X` in the URL to center the view on a specific block.
4. **Inspect Block:** Click on any block card to slide open the **Block Inspector Drawer**:
   - Inspect the block's sequence ID, operation type, actor, and timestamp.
   - Click the hash fields to view the full 64-character SHA-256 digests.
   - Review the **Before / After Payload Diff** to see exactly which fields were altered.

---

## 9. Auditor Audit Log Table & Deep Forensic Scrubbing

### What It Is For
Enables rapid filtering, searching, and cross-investigation across thousands of historical audit events.

### How to Use It
1. Navigate to **[http://localhost:5173/auditor/log](http://localhost:5173/auditor/log)**.
2. **Filter Toolbar:** Filter by Action (`INSERT`, `UPDATE`, `DELETE`), Table name (`employees`, `salary_history`), or Severity (`INFO`, `WARNING`, `CRITICAL`).
3. **Deep Link Navigation:**
   - Click the **"Chain"** button on any row to open that exact block in the Chain Explorer (`/auditor/chain?seq=X`).
   - Click the **"Time-Travel"** button on any employee update to reconstruct their profile as of that exact second.
4. **Tamper Highlighting:** If a block has been tampered with, its row glows in high-contrast crimson with a `[TAMPERED]` badge.

---

## 10. Historical Time-Travel State Reconstruction

### What It Is For
In legal audits or dispute investigations (e.g., wrongful termination, salary disputes, or unauthorized privilege escalation), organizations need to know: *"What was this employee's exact role, department, salary, and status on March 15th at 2:30 PM?"* Standard databases only store the current state (`UPDATE` overwrites the past).

Argus implements `reconstruct_employee_state(emp_id, as_of)`:
- Executes a stored procedure that starts from the employee's initial `INSERT` audit block and sequentially applies all JSONB mutation deltas up to the requested timestamp.
- Reconstructs the exact past state without relying on mutable snapshot tables.

### How to Use It
1. Navigate to **[http://localhost:5173/auditor/time-travel](http://localhost:5173/auditor/time-travel)**.
2. Select an employee from the dropdown list.
3. Choose a point on the interactive **Mutation Timeline** or pick a custom date and time.
4. Click **"Reconstruct Record"**.
5. The **Reconstructed State Card** instantly displays the employee's historical title, department, salary, and active status as of that exact moment.

---

## 11. Automated Risk & Fraud Detection Engine

### What It Is For
Eliminates the need for auditors to manually inspect thousands of routine transactions. Argus continuously scans the audit log for known fraud and exfiltration patterns:
1. **Salary Spikes:** Automatically flags any salary increase or decrease exceeding 30% (`salary_change_exceeds_30_percent`).
2. **Mass Deletions:** Automatically flags when 3 or more employee deletions occur within a rolling 1-hour window (`mass_employee_deletions`).

### How to Use It
1. Navigate to **[http://localhost:5173/auditor/risk](http://localhost:5173/auditor/risk)**.
2. View pending flags organized into cards with severity badges and detailed context.
3. Click the **"Audit Seq: #X"** link to inspect the offending audit block.
4. To acknowledge an alert after investigation, click **"Mark Safe / Reviewed"**. The system records the auditor's user ID and timestamp.

---

## 12. Self-Contained Cryptographic Evidence Pack Export

### What It Is For
External regulatory bodies (SEC, FTC, EU Data Protection Authorities, external accounting firms) need to audit corporate compliance without receiving direct SSH/database credentials to internal networks.

Argus generates a self-contained `.arguspack` archive:
- **`manifest.json`:** Contains metadata, public keys, and cryptographic digest summaries.
- **`events.jsonl`:** Canonical serialization of all audit entries.
- **`checkpoints.jsonl`:** Checkpoint tree and root hashes.
- **`anchor_proof.json`:** External anchor verification proofs.
- **`signature.sig`:** Ed25519 digital signature of the canonical dataset.
- **`verify.py`:** A standalone, zero-dependency Python script that the regulator can run on their own air-gapped machine to verify the entire archive.

### How to Use It
1. In the Auditor Portal, click **"Export Evidence Pack"** in the top navigation or call:
   ```bash
   GET /api/audit-logs/export
   ```
2. The browser downloads the signed `.arguspack` archive.
3. Regulators can extract the zip archive and run `python verify.py` to cryptographically prove chain authenticity.

---

## 13. High-Throughput Concurrency Lab

### What It Is For
Proves that Argus's Two-Phase Locking (2PL) write serialization on `chain_state` operates flawlessly under high-throughput concurrent loads without deadlock, race conditions, or hash chain branching.

### How to Use It
1. Open the Auditor Portal and navigate to **Concurrency Lab** (`/auditor/concurrency`) or run the benchmark tool:
   ```powershell
   .\.venv\Scripts\python.exe db/bench/run_full_benchmarks.py
   ```
2. Dispatch 20 concurrent transactions.
3. Observe the sequential assignment of sequence IDs and the 100% intact hash chain.

---

## 14. Out-of-Band Red Team Adversary Simulation CLI

### What It Is For
Provides an interactive demonstration tool simulating real-world insider attacks directly against the PostgreSQL engine as a rogue DBA, showcasing how Argus catches each attack in real time.

### Available Attack Scenarios

| Scenario | Command | What It Simulates | How Argus Detects It |
|---|---|---|---|
| **1. Direct Row Mutation** | `python -m db.cli.adversary attack --scenario dba-row-tamper --seq 29` | Rogue DBA modifies salary in historical audit row via raw SQL. | Internal Hash Mismatch: $H_{29} \ne \text{SHA256}(H_{28} \| S(R_{29}))$. Visualized in crimson on UI. |
| **2. Recompute and Hide** | `python -m db.cli.adversary attack --scenario recompute-and-hide --seq 29` | Rogue DBA alters a row and recalculates all forward hashes to the tail. | External Anchor Store Mismatch: Tail hash fails to match the signed external anchor log. |
| **3. Checkpoint Forgery** | `python -m db.cli.adversary attack --scenario checkpoint-forgery` | Attacker forges a checkpoint record in PostgreSQL. | Ed25519 Signature Failure: Digital signature rejected by public key verification. |
| **4. Delete Audit Row** | `python -m db.cli.adversary attack --scenario delete-audit-row --seq 29` | Rogue DBA deletes an incriminating audit row. | Sequence Gap & Orphan Detection: Sequence skips from 28 to 30, and $H_{30}$'s previous hash does not match $H_{28}$. |
| **Heal / Restore** | `python -m db.cli.adversary heal` | Restores pristine pre-attack snapshot. | Verifier confirms 100% intact chain and clean anchor match. |

---

## Complete Viva & Interview Demonstration Runbook

Follow this step-by-step walkthrough during an evaluation, presentation, or interview to deliver a high-impact, professional demonstration:

### Step 1: Establish the Baseline Normal State (60 Seconds)
1. Open browser to **[http://localhost:5173/auditor/overview](http://localhost:5173/auditor/overview)**.
2. Point out:
   - **System Integrity:** Displays **"INTACT"** (emerald green badge).
   - **External Anchor Status:** Displays **"MATCH"** (green shield).
   - **Sidebar Status:** Displays **"Active Monitoring"**.
3. Click **"Run Verification"** to show a live walk across all 51 audit records completing in milliseconds.

### Step 2: Demonstrate Everyday HR Operations (60 Seconds)
1. Navigate to **[http://localhost:5173/admin/employees](http://localhost:5173/admin/employees)**.
2. Click **"Edit Salary"** on an employee, change the salary from \$50,000 to \$55,000, and save.
3. Navigate immediately to **[http://localhost:5173/auditor/chain](http://localhost:5173/auditor/chain)**.
4. Show the new block at the top of the chain with the updated salary in the before/after diff.

### Step 3: Demonstrate Attack Scenario 1 — Rogue DBA Direct Row Tamper (2 Minutes)
1. Open PowerShell and run:
   ```powershell
   $env:PYTHONPATH="."; & .\.venv\Scripts\python.exe -m db.cli.adversary attack --scenario dba-row-tamper --seq 29
   ```
2. Switch to the browser at `http://localhost:5173/auditor/overview`.
3. Within seconds (or on clicking "Run Verification"):
   - The status transitions to **`COMPROMISED`** in glowing crimson.
   - The top banner flashes: **`CRITICAL SECURITY INCIDENT DETECTED`**.
   - The banner CTA button reads: **`Inspect Compromised Block #29 →`**.
4. Click the CTA button:
   - The browser deep-links to `/auditor/chain?seq=29`.
   - Sequence #29 is highlighted in crimson with a `[TAMPERED]` pill badge.
   - Opening the Block Inspector Drawer reveals the stored hash vs. recomputed hash mismatch.

### Step 4: Demonstrate Attack Scenario 2 — Forward Hash Recalculation (2 Minutes)
1. Run:
   ```powershell
   $env:PYTHONPATH="."; & .\.venv\Scripts\python.exe -m db.cli.adversary attack --scenario recompute-and-hide --seq 29
   ```
2. In the browser:
   - The internal hash chain appears superficially valid because the attacker recalculated the forward hashes.
   - **HOWEVER, the External Anchor Store displays `MISMATCH` in bright red!**
   - The top banner warns: **`EXTERNAL ANCHOR MISMATCH: Database tail hash deviates from immutable Ed25519 anchor log.`**
3. Explain to the audience:
   > *"This proves that even if an attacker has root database access and recalculates every single hash inside PostgreSQL, they cannot compromise Argus because our Ed25519 signed anchor exists outside the database."*

### Step 5: Heal and Restore to 100% Pristine State (30 Seconds)
1. In PowerShell, run:
   ```powershell
   $env:PYTHONPATH="."; & .\.venv\Scripts\python.exe -m db.cli.adversary heal
   ```
2. Refresh the browser:
   - All banners disappear.
   - Status returns to **`INTACT`** (emerald green).
   - Anchor returns to **`MATCH`**.
   - Chain status returns to **`Active Monitoring`**.

---

## Technical Appendix: File & Module Architecture

- **PostgreSQL Migrations & Triggers:** [`db/alembic/versions/`](file:///c:/dev/Argus/db/alembic/versions/)
- **Core Stored Routines:** [`db/alembic/versions/009_stored_routines.py`](file:///c:/dev/Argus/db/alembic/versions/009_stored_routines.py)
- **Role Permissions Script:** [`db/scripts/setup_roles.sql`](file:///c:/dev/Argus/db/scripts/setup_roles.sql)
- **Standalone Hash Verifier:** [`db/cli/hash_verifier.py`](file:///c:/dev/Argus/db/cli/hash_verifier.py)
- **Ed25519 Signer Utility:** [`db/cli/signer.py`](file:///c:/dev/Argus/db/cli/signer.py)
- **Adversary Simulation CLI:** [`db/cli/adversary.py`](file:///c:/dev/Argus/db/cli/adversary.py)
- **FastAPI Core & Routers:** [`api/main.py`](file:///c:/dev/Argus/api/main.py), [`api/routers/audits.py`](file:///c:/dev/Argus/api/routers/audits.py)
- **Frontend App Router & Layout:** [`frontend/src/App.tsx`](file:///c:/dev/Argus/frontend/src/App.tsx), [`frontend/src/layouts/AuditorLayout.tsx`](file:///c:/dev/Argus/frontend/src/layouts/AuditorLayout.tsx)
- **Dedicated Chain Explorer:** [`frontend/src/pages/auditor/AuditChainPage.tsx`](file:///c:/dev/Argus/frontend/src/pages/auditor/AuditChainPage.tsx)
- **Time-Travel Forensic View:** [`frontend/src/components/auditor/TimeTravelView.tsx`](file:///c:/dev/Argus/frontend/src/components/auditor/TimeTravelView.tsx)
- **Risk & Anomaly Panel:** [`frontend/src/components/auditor/RiskPanel.tsx`](file:///c:/dev/Argus/frontend/src/components/auditor/RiskPanel.tsx)
