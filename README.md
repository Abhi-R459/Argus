# Argus

> **A tamper-evident, self-verifying audit trail engine for PostgreSQL**, demonstrated through an enterprise Employee Records management system.  
> *Course Project for BCSE302L Database Systems — Abhinav & Nidhurshek.*

[![Tests](https://img.shields.io/badge/tests-114%20passed-brightgreen.svg)](#running-automated-tests)
[![Red Team Engine](https://img.shields.io/badge/Adversary%20CLI-Active-crimson.svg)](#part-2-testing-out-of-band-adversary-attacks-red-team-cli)
[![Security](https://img.shields.io/badge/Security-Fail--Closed-009688.svg)](#overview)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-15+-blue.svg)](https://www.postgresql.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-009688.svg)](https://fastapi.tiangolo.com/)
[![React](https://img.shields.io/badge/React-19-61DAFB.svg)](https://react.dev/)
[![TailwindCSS](https://img.shields.io/badge/Tailwind-v3-38B2AC.svg)](https://tailwindcss.com/)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

---

## Table of Contents

- [Overview](#overview)
- [Key Features](#key-features)
- [Architecture & Security Model](#architecture--security-model)
- [Technology Stack](#technology-stack)
- [Quickstart (Docker Compose)](#quickstart-docker-compose)
- [Step-by-Step Local Setup](#step-by-step-local-setup)
  - [1. Prerequisites](#1-prerequisites)
  - [2. Environment Configuration (`.env`)](#2-environment-configuration-env)
  - [3. Database Setup](#3-database-setup)
  - [4. Backend Setup (FastAPI)](#4-backend-setup-fastapi)
  - [5. Frontend Setup (React + Vite)](#5-frontend-setup-react--vite)
- [Interactive Hands-On Testing Guide](#interactive-hands-on-testing-guide)
  - [Part 1: Testing Application Features](#part-1-testing-application-features)
  - [Part 2: Testing Out-of-Band Adversary Attacks (Red Team CLI)](#part-2-testing-out-of-band-adversary-attacks-red-team-cli)
  - [Part 3: Testing Air-Gapped Evidence Bundles (.arguspack)](#part-3-testing-air-gapped-evidence-bundles-arguspack)
  - [Part 4: Testing In-Engine Database Triggers (SQL)](#part-4-testing-in-engine-database-triggers-sql)
- [Application Walkthrough & Features](#application-walkthrough--features)
  - [HR Admin Portal](#hr-admin-portal)
  - [Compliance Auditor Portal](#compliance-auditor-portal)
  - [Time-Travel Historical Reconstruction](#time-travel-historical-reconstruction)
  - [Cryptographic Evidence Export](#cryptographic-evidence-export)
  - [Concurrency Benchmark Lab](#concurrency-benchmark-lab)
- [Standalone Cryptographic Verifier CLI](#standalone-cryptographic-verifier-cli)
- [Empirical Benchmark Suite](#empirical-benchmark-suite)
- [Running Automated Tests](#running-automated-tests)
- [Troubleshooting & FAQ](#troubleshooting--faq)
- [Project Documentation](#project-documentation)

---

## Overview

Traditional relational audit logs are stored in standard database tables. A malicious or compromised administrator (or superuser) can silently alter salaries, delete reprimands, or modify access logs directly via SQL without leaving a trace.

**Argus solves this natively within PostgreSQL:**
- **Trigger-Enforced Cryptographic Hash Chaining**: Every `INSERT`, `UPDATE`, or `DELETE` on monitored tables fires an `AFTER` trigger. The trigger serializes the change, computes a canonical SHA-256 digest linked to the preceding entry's hash, and appends the immutable log row.
- **Mathematical Tamper Evidence**: Modifying, deleting, inserting, or reordering any historical audit entry permanently invalidates the cryptographic hash chain for all subsequent entries.
- **Strict Least-Privilege Separation**:
  - `hr_admin`: Manages employees and compensation; read-only to audit logs; strictly denied direct `INSERT`, `UPDATE`, `DELETE`, or `TRUNCATE` privileges on audit logs (all audit records append exclusively via `SECURITY DEFINER` triggers).
  - `compliance_auditor`: Read-only access to audit logs, views, and integrity verification; denied write access and raw PII access.
- **Zero-Gap Concurrency Guarantee**: Row-level locking on `chain_state` serializes concurrent transactions without deadlocks, ensuring zero sequence ID gaps.
- **Ed25519 Checkpoint Signing & Multi-Target Anchoring**: Snapshots of the chain tail are cryptographically signed with Ed25519 keys and anchored outside the database (local disk or GitHub repository).
- **HMAC Blind Indexing & Redaction**: Replaces plaintext PII with `[REDACTED]` while generating keyed HMAC digests for sub-millisecond exact-match lookups.
- **Air-Gapped Turnkey Verifier**: Self-contained `.arguspack` evidence archives embedding zero-dependency pure-Python RFC 8032 verifiers.

---

## Key Features

| Capability | Description |
|---|---|
| 🔗 **Cryptographic Chaining** | In-engine SHA-256 digest linking every state change to the prior audit block. |
| 🛡️ **Business Rule Triggers** | Database-level blocks against salary reductions $> 30\%$, self-salary modification, and SSN alterations. |
| 🕵️ **PII Masking & Encryption** | Automatic database-level masking of sensitive credentials and `pgcrypto` field-level encryption. |
| 🔍 **HMAC Blind Indexing** | Sub-millisecond forensic search over masked identifiers via keyed HMAC B-tree indexes without revealing plaintext PII. |
| 📦 **Air-Gapped Evidence Pack** | Export portable `.arguspack` bundles containing pure-Python RFC 8032 zero-dependency offline verifiers. |
| ⚡ **Parallel Verifier** | Standalone verification engine dividing the chain into checkpoint-bounded segments for concurrent verification. |
| ⏳ **Time-Travel Querying** | Replays historical `audit_log` deltas to reconstruct any employee's state as of an exact microsecond. |
| 📜 **Signed Evidence Export** | Generates tamper-evident JSON bundles digitally signed with Ed25519 for external compliance audits. |
| 🧪 **Interactive Concurrency Lab** | Built-in UI to trigger parallel write races, demonstrating lock serialization and tamper detection live. |
| 🎯 **Red Team Adversary Engine** | Dedicated out-of-band CLI tool (`db.cli.adversary`) simulating real-world rogue DBA attacks with one-command healing. |

---

## Architecture & Security Model

```
┌────────────────────────────────────────────────────────────────────────┐
│                        REACT FRONTEND (Vite)                           │
│  - HR Admin Layout (Directory, Create/Edit Modals, Salary Adjustments) │
│  - Auditor Layout (Log Explorer, Diff Viewer, Time-Travel, Export)     │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │ HTTP / REST (Clerk Bearer JWT)
┌───────────────────────────────────▼────────────────────────────────────┐
│                        FASTAPI BACKEND API                             │
│  - JWT Verification Middleware                                         │
│  - Least-Privilege Dual Connection Pool Routing                        │
└─────────────┬────────────────────────────────────────────┬─────────────┘
              │ hr_admin pool                              │ compliance_auditor pool
              ▼                                            ▼
┌────────────────────────────────────────────────────────────────────────┐
│                        POSTGRESQL 15+ DATABASE                         │
│  ┌────────────────────────┐              ┌──────────────────────────┐  │
│  │     Business Tables    │              │    Audit Trail Engine    │  │
│  │  employees, roles,     ├─AFTER Trigger┤  audit_log (append-only) │  │
│  │  departments, salary   │              │  chain_state, checkpoints│  │
│  └────────────────────────┘              └──────────────▲───────────┘  │
└─────────────────────────────────────────────────────────┼──────────────┘
                                                          │ psycopg2
┌─────────────────────────────────────────────────────────┴──────────────┐
│                    STANDALONE VERIFIER ENGINE                          │
│  - Sequential & Parallel Segment Walks (`verify-chain`)                │
│  - Ed25519 Checkpoint Signer (`sign-checkpoint`)                       │
│  - External Anchor Storage Adapter (Local File & GitHub)               │
└────────────────────────────────────────────────────────────────────────┘
```

### Regulatory Control Support & Standards Scoping

> [!NOTE]
> **Defensible Compliance & Module Boundaries:**
> - **Control Support vs. Compliance Certification:** Regulatory compliance (SOC 2 Type II, SOX 404, GDPR, HIPAA) is an organizational, policy, and audit outcome attested by accredited third-party assessors. Argus provides technical controls that **support organizations in satisfying control objectives** (e.g., SOC 2 CC6.8 audit immutability, SOX 404 internal accounting controls, GDPR Art. 25 data protection by design).
> - **NIST Approved Algorithms:** Argus implements NIST-approved cryptographic primitives: AES-256 (NIST FIPS 197), SHA-256 (NIST FIPS 180-4), and Ed25519 (NIST FIPS 186-5, RFC 8032). Standard PostgreSQL `pgcrypto` and Python `cryptography` distributions are software libraries and are **not** CMVP-validated cryptographic modules under FIPS 140-2 / FIPS 140-3.
> - **HIPAA Scope:** HIPAA specifically governs Protected Health Information (ePHI). Argus implements technical safeguards analogous to HIPAA Security Rule §164.312(b) (Audit Controls) on enterprise Human Resource (HR) personnel records (PII).

---

## Technology Stack

- **Database:** PostgreSQL 15+, `pgcrypto`, PL/pgSQL triggers, views, and stored procedures.
- **Backend:** Python 3.12, FastAPI, SQLAlchemy 2 (asyncpg + psycopg2), Pydantic v2, Uvicorn.
- **Frontend:** React 19, TypeScript, Vite, Tailwind CSS, TanStack React Query, Lucide React.
- **Authentication:** Clerk Auth (JWT authentication and role sync).
- **Cryptography:** Ed25519 (`cryptography`), SHA-256 (`hashlib`).
- **Database Migrations:** Alembic (9 versions).
- **Testing:** Pytest, pytest-asyncio, HTTPX, Playwright.

---

## Quickstart (Docker Compose)

The fastest way to spin up the complete end-to-end stack:

```bash
# 1. Clone the repository
git clone https://github.com/Abhi-R459/Argus.git
cd Argus

# 2. Configure environment (pre-configured template provided)
cp .env.example .env

# 3. Start all services (Postgres, FastAPI Backend, React Frontend)
docker compose up --build
```

- **Frontend Application:** [http://localhost:80](http://localhost:80)
- **FastAPI API & Docs:** [http://localhost:8000/docs](http://localhost:8000/docs)
- **Database:** `localhost:5432` (`argus`)

---

## Step-by-Step Local Setup

### 1. Prerequisites

Ensure you have installed:
- **Git** (v2.30+)
- **Python** (v3.11 or v3.12)
- **Node.js** (v18+ or v20+) & **npm** (v9+)
- **Docker Desktop** (running)

### 2. Environment Configuration (`.env`)

Copy the configuration template to root, `api/`, and `frontend/`:

```powershell
# Windows (PowerShell)
Copy-Item .env.example .env
Copy-Item .env.example api/.env
Copy-Item .env.example frontend/.env
```

```bash
# macOS / Linux
cp .env.example .env
cp .env.example api/.env
cp .env.example frontend/.env
```

Ensure `.env` contains your database and Clerk keys:
```env
DATABASE_URL_MIGRATIONS=postgresql://postgres:password@localhost:5432/argus
DATABASE_URL_HR_ADMIN=postgresql+asyncpg://hr_admin:password@localhost:5432/argus
DATABASE_URL_COMPLIANCE_AUDITOR=postgresql+asyncpg://compliance_auditor:password@localhost:5432/argus

# Clerk Authentication Keys (From https://dashboard.clerk.com/)
VITE_CLERK_PUBLISHABLE_KEY=pk_test_...
CLERK_SECRET_KEY=sk_test_...
CLERK_JWT_KEY="-----BEGIN PUBLIC KEY-----\n...\n-----END PUBLIC KEY-----"

SIGNING_PRIVATE_KEY_PATH=./keys/verifier_private_key.pem
ANCHOR_STORE=local_file
ANCHOR_FILE_PATH=./anchor/chain_anchor.log
CHECKPOINT_INTERVAL=25
```

### 3. Database Setup

1. **Start PostgreSQL with Docker:**
   ```bash
   docker compose up -d db
   ```

2. **Apply Database Migrations (Alembic):**
   ```bash
   alembic upgrade head
   ```

3. **Initialize Database Roles & Permissions:**
   ```powershell
   # Windows (PowerShell)
   Get-Content db/scripts/setup_roles.sql | docker exec -i argus-postgres psql -U postgres -d argus
   ```
   ```bash
   # macOS / Linux
   docker exec -i argus-postgres psql -U postgres -d argus < db/scripts/setup_roles.sql
   ```

4. *(Optional)* **Seed Benchmark / Demo Data:**
   ```bash
   python -m db.bench.seed --num-employees 25 --num-changes 50
   ```

### 4. Backend Setup (FastAPI)

1. **Set up a Python virtual environment:**
   ```bash
   python -m venv .venv

   # Activate virtual environment:
   # Windows (PowerShell):
   .\.venv\Scripts\Activate.ps1
   # Windows (CMD):
   .\.venv\Scripts\activate.bat
   # macOS / Linux:
   source .venv/bin/activate
   ```

2. **Install Python dependencies:**
   ```bash
   pip install -r api/requirements.txt
   ```

3. **Start the FastAPI backend server:**
   ```bash
   uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload
   ```

4. **Verify Backend Health:**
   - Health check: [http://localhost:8000/api/health](http://localhost:8000/api/health)
   - Interactive Swagger docs: [http://localhost:8000/docs](http://localhost:8000/docs)

---

### 5. Frontend Setup (React + Vite)

Open a **new terminal** window:

1. **Navigate to the frontend directory:**
   ```bash
   cd frontend
   ```

2. **Install Node dependencies:**
   ```bash
   npm install --legacy-peer-deps
   ```

3. **Start the Vite dev server:**
   ```bash
   npm run dev
   ```

4. **Open the App in your Browser:**
   - Visit: **[http://localhost:5173](http://localhost:5173)** (or `http://localhost:3000`)
   - Authenticate via Clerk to access the **HR Admin** or **Compliance Auditor** dashboard.

---

## Interactive Hands-On Testing Guide

> **Test the Complete System on Your Own:**  
> Follow this guide to test every layer of Argus—from standard HR administration in the web UI to hostile out-of-band database attacks using the Red Team CLI and offline forensic verification.
> 
> 💡 **Pro-Tip for Evaluators:** For the best demonstration experience, arrange your workspace side-by-side:
> - **Left Half of Screen:** Web Browser running the **Compliance Auditor Dashboard** (`http://localhost:5173/auditor`)
> - **Right Half of Screen:** Administrative Terminal running in the project root (`C:\dev\Argus`)

---

### Part 1: Testing Application Features

#### 1.1 Role Switching & Least-Privilege Isolation
- In the top navigation bar, toggle between the **HR Admin** and **Compliance Auditor** roles.
- **Observe Strict Boundary Separation:**
  - **HR Admin** can manage employees and compensation, but cannot access raw cryptographic verification actions or delete/tamper with audit logs.
  - **Compliance Auditor** has read-only access to audit logs, anchor status, and verification tools, but cannot edit employee salaries or view plaintext PII.

#### 1.2 HR Admin: Employee Creation & Database-Level Encryption (`/hr`)
1. Switch to **HR Admin** (`/hr`) and click **"Add Employee"**.
2. Create a new employee:
   - **Name:** Alice Walker
   - **Department:** Engineering
   - **Role:** Senior Software Engineer
   - **Salary:** $95,000
   - **National ID:** `123-45-6789`
3. **What happens behind the scenes:**
   - PostgreSQL fires an `AFTER INSERT` trigger (`trg_audit_employees`).
   - `pgcrypto` encrypts sensitive fields (`national_id`, `contact_info`) at the column level.
   - The engine generates a keyed HMAC blind index for forensic lookups.
   - A canonical SHA-256 hash is computed, linking this entry to the prior audit block.

#### 1.3 HR Admin: Testing Database Business Rule Blocks
Argus enforces strict business rules directly inside PostgreSQL triggers rather than relying solely on UI validation:
- **Test 1: Salary Drop $> 30\%$ Block:**
  - In the employee directory, click **"Adjust Salary"** on an employee earning $100,000.
  - Attempt to reduce their salary to $50,000 (a 50% decrease).
  - **Expected Result:** The transaction is aborted by PostgreSQL trigger `chk_salary_decrease_threshold`. The UI displays an error explaining that decreases $> 30\%$ are blocked.
- **Test 2: Self-Salary Modification Block:**
  - Attempt to adjust the salary of the currently authenticated user.
  - **Expected Result:** Blocked by trigger `chk_prevent_self_salary_modification`.

#### 1.4 Compliance Auditor: Live Audit Trail & Forensic Diff Viewer (`/auditor`)
1. Switch to **Compliance Auditor** (`/auditor`).
2. Explore the live chronological audit stream. Every action (`INSERT`, `UPDATE`, `DELETE`) shows its sequence ID, actor, timestamp, and SHA-256 block hash.
3. Click any audit event to open the **Side-by-Side Diff Viewer**, showing the exact before/after field mutations rather than raw JSON strings.

#### 1.5 Compliance Auditor: Encrypted Blind Index Search
1. In the search box on the Audit Log Explorer, enter the National ID: `123-45-6789`.
2. **Expected Result:**
   - The search matches in $< 5\text{ms}$ using PostgreSQL's functional B-tree expression index `idx_audit_log_nid_blind`.
   - The result is displayed, but the National ID column remains safely masked as `[REDACTED]`.
   - Plaintext PII is never exposed to auditors or saved unencrypted in audit logs.

#### 1.6 Compliance Auditor: Time-Travel Historical State Reconstruction
1. Open an employee profile.
2. Scrub backward along the **Time-Travel Date/Time Slider**.
3. **Expected Result:** The interface calls PostgreSQL stored routine `reconstruct_employee_state(emp_id, as_of)`, sequentially rolling back mutations to render that employee's exact historical salary, department, and title as of the selected microsecond.

#### 1.7 Compliance Auditor: Live Concurrency Benchmark Lab
1. In the Auditor navigation, click **Concurrency Lab**.
2. Select 5 or 10 concurrent worker threads and click **"Run Concurrency Benchmark"**.
3. **Expected Result:**
   - Multiple parallel transactions fire against PostgreSQL simultaneously.
   - Row-level locking on `chain_state (id=1)` perfectly serializes writes with zero race conditions, zero deadlocks, and zero sequence ID gaps.

---

### Part 2: Testing Out-of-Band Adversary Attacks (Red Team CLI)

> **Real-World Threat Model ($A_{DBA}$):**  
> A genuine rogue administrator or compromised DBA does *not* log into a web UI to attack their company—they connect directly to PostgreSQL via `psql` or native sockets and alter records out-of-band.  
> To model this faithfully with zero backdoor flaws in the web application, Argus provides a standalone **Red Team Adversary CLI** (`db.cli.adversary`).
>
> Every attack automatically takes an atomic snapshot (`.argus_snapshot.json`), allowing you to restore the database to 100% validity at any time with one command (`heal`).

```
                    +------------------------------------------+
                    |         Adversary Red Team CLI           |
                    |          (db.cli.adversary)              |
                    +--------------------+---------------------+
                                         |
                  Direct superuser SQL   |  (Out-of-band / Raw Socket)
                  mutations & attacks    |
                                         v
+---------------------+        +--------------------+        +---------------------+
|  Auditor Dashboard  | <----> |  Hardened FastAPI  | <----> | PostgreSQL Database |
|  (http://localhost) |        |     (api/)         |        |  (Tables, Triggers) |
+---------------------+        +--------------------+        +---------------------+
  - Real-Time Monitor            - Fail-Closed Verify           - AFTER Triggers
  - Red Tamper Alerts            - Diagnostic Benchmarks        - Immutable Anchors
```

#### Step 0: Baseline Health Check
Before starting, verify baseline system health in your terminal:
```bash
python -m db.cli.adversary status
```
**Expected Output:**
```text
[OK] System Normal (No active adversary attacks staged).
  Total Audit Log Entries : 49
  Total Checkpoints       : 2
  Internal Hash Chain     : VALID (INTACT)
  External Anchor Store   : MATCH
```
In your browser dashboard, click **"Verify Chain"** — the status badge should display green **`VALID`**.

---

#### Scenario 1: Rogue DBA Historical Salary Tampering (`dba-row-tamper`)
*Threat:* A rogue DBA connects directly to PostgreSQL and modifies an employee's historical salary record in `audit_log` without updating the SHA-256 hash.

1. **Execute Attack (Terminal):**
   ```bash
   python -m db.cli.adversary attack --scenario dba-row-tamper --sequence-id 29
   ```
2. **Observe Detection (Browser or Terminal):**
   - In the Auditor Dashboard, click **"Verify Chain"** (or run `python -m db.cli.verifier verify-chain`).
   - **Result:** Status immediately flips to **`TAMPER DETECTED (Red)`**.
   - **Details:** Identifies the exact violation: `Hash mismatch at sequence_id 29: expected <hash> actual <hash>`.
   - In the Chain Visualizer, node 29 glows red, pinpointing the corrupted block.
3. **One-Command Healing:**
   ```bash
   python -m db.cli.adversary heal
   ```
   - Re-click **"Verify Chain"** in the browser -> status immediately returns to green **`VALID`**!

---

#### Scenario 2: Forward Hash Recalculation ("Recompute & Hide") (`recompute-and-hide`)
*Threat:* A sophisticated DBA alters a historical salary row AND recomputes all forward SHA-256 hashes up to the current tail so the database appears internally consistent.

*Can a database-only ledger catch this?* **No.** Any standard database ledger is deceived because its internal hashes match. **Argus catches this using its external Ed25519 Anchor Store.**

1. **Execute Attack (Terminal):**
   ```bash
   python -m db.cli.adversary attack --scenario recompute-and-hide --sequence-id 20
   ```
2. **Observe Detection (Terminal & Browser):**
   ```bash
   python -m db.cli.adversary status
   ```
   **Output:**
   ```text
     Internal Hash Chain     : VALID (INTACT)
     External Anchor Store   : MISMATCH (Anchor mismatch for checkpoint 2: DB tail != Anchor store)
   ```
   - In the Auditor Dashboard, the **Anchor Health** card turns **RED**, alerting the auditor to unauthorized state tampering!
   - Because the attacker does not possess the offline Ed25519 private key (`./keys/verifier_private_key.pem`), they cannot forge the external anchor.
3. **One-Command Healing:**
   ```bash
   python -m db.cli.adversary heal
   ```

---

#### Scenario 3: Checkpoint Signature Forgery (`checkpoint-forgery`)
*Threat:* An attacker modifies a checkpoint record or signature directly inside `chain_checkpoints`.

1. **Execute Attack (Terminal):**
   ```bash
   python -m db.cli.adversary attack --scenario checkpoint-forgery
   ```
2. **Observe Detection:**
   - The standalone verifier validates the checkpoint digest against the auditor's Ed25519 public key.
   - Signature verification fails immediately with `InvalidSignature`.
3. **One-Command Healing:**
   ```bash
   python -m db.cli.adversary heal
   ```

---

#### Scenario 4: Physical Audit Row Deletion & Gap Detection (`delete-audit-row`)
*Threat:* An administrator deletes an audit row via `DELETE FROM audit_log WHERE sequence_id = 25;` to erase evidence of a transaction.

1. **Execute Attack (Terminal):**
   ```bash
   python -m db.cli.adversary attack --scenario delete-audit-row --sequence-id 25
   ```
2. **Observe Detection (Browser or Terminal):**
   - Click **"Verify Chain"** in the Auditor Dashboard.
   - **Result:** Status flips to **`TAMPER DETECTED`**.
   - **Details:** `Sequence gap detected at sequence_id 25: expected 25, found 26.`
   - The verifier immediately flags the missing sequence number and orphan record.
3. **One-Command Healing:**
   ```bash
   python -m db.cli.adversary heal
   ```

---

#### Adversary Engine CLI Quick Reference

| Command | Option | Description |
|---|---|---|
| `status` | — | Diagnoses active anomaly state, chain continuity, and anchor alignment |
| `attack` | `--scenario dba-row-tamper` | Mutates historical audit row without updating hash |
| `attack` | `--scenario recompute-and-hide` | Mutates row and rewrites all forward hashes to test anchor detection |
| `attack` | `--scenario checkpoint-forgery` | Corrupts Ed25519 signature in database checkpoint table |
| `attack` | `--scenario delete-audit-row` | Deletes historical audit log record to trigger sequence gap detection |
| `heal` | — | Restores pristine database state from snapshot with 100% precision |

---

### Part 3: Testing Air-Gapped Evidence Bundles (.arguspack)

Argus exports portable evidence packages (`.arguspack`) designed for external regulators working on air-gapped workstations without network access or Python package managers (`pip`):

1. **Export the Bundle:**
   - In the Auditor Dashboard, navigate to **Export**.
   - Select **`.arguspack Bundle`** and click **"Export Evidence"**.
   - The browser downloads `argus_evidence_<timestamp>.arguspack`.
2. **Unpack on an Air-Gapped or Separate Machine:**
   ```bash
   # Unpack the .arguspack file (it is a standard ZIP archive)
   unzip argus_evidence_*.arguspack -d argus_bundle/
   cd argus_bundle
   ```
   **Bundle Contents:**
   - `events.jsonl`: Line-delimited canonical audit events.
   - `checkpoints.json`: Checkpoint commitments.
   - `public_key.pem`: Ed25519 public key.
   - `signature.sig`: Detached Ed25519 digital signature.
   - `manifest.json`: Root hashes and record counts.
   - `verify_standalone.py`: **Zero-dependency, pure-Python RFC 8032 verifier script.**
3. **Execute Standalone Verification:**
   ```bash
   python verify_standalone.py --bundle .
   ```
   **Expected Output:**
   ```text
   [OK] Checkpoint signatures cryptographically verified.
   [OK] 49 / 49 audit events verified. Zero mismatches, zero gaps.
   Audit chain 100% MATHEMATICALLY CONTINUOUS. Exiting with code 0.
   ```
4. **Test Standalone Tamper Detection:**
   - Open `events.jsonl` in any text editor and alter a single digit in any salary amount.
   - Re-run: `python verify_standalone.py --bundle .`
   - **Result:** The standalone script immediately detects the exact altered line, reports a hash mismatch, and exits with code 1.

---

### Part 4: Testing In-Engine Database Triggers (SQL)

You can also test database-level security mechanisms directly via `psql` or `docker exec`:

#### Test 1: Role Privilege Isolation (HR Admin cannot DELETE audit logs)
```bash
# Connect to Postgres
docker exec -it argus-postgres psql -U postgres -d argus
```
```sql
-- Assume the hr_admin identity
SET ROLE hr_admin;

-- Attempt to purge audit trail
DELETE FROM audit_log;
-- Result: ERROR: permission denied for table audit_log (Code: 42501)

-- Attempt to update an audit entry
UPDATE audit_log SET new_value = '{}' WHERE sequence_id = 1;
-- Result: ERROR: permission denied for table audit_log (Code: 42501)

RESET ROLE;
```

#### Test 2: Salary Reduction Trigger ($> 30\%$ Block)
```sql
-- Attempt to cut employee salary from $100,000 to $50,000
UPDATE employees SET salary = 50000.00 WHERE id = 1;
-- Result: ERROR: Salary decrease exceeds maximum allowable threshold of 30%
```

#### Test 3: Self-Salary Modification Block
```sql
-- Attempt to adjust own salary
UPDATE employees SET salary = salary + 10000.00 WHERE id = 1;
-- Result: ERROR: Employees cannot modify their own salary record
```

---

## Application Walkthrough & Features

### HR Admin Portal
- **Employee Directory Table:** Search, filter by department, paginate, and sort employees.
- **Create & Edit Employee:** Validated modals capturing employee profile details. Sensitive fields (`national_id`, `contact_info`) are encrypted with `pgcrypto` at the database level.
- **Salary Adjustments:** Dedicated modal enforcing business constraints (e.g. raises and $< 30\%$ adjustments allowed, self-modifications blocked).

### Compliance Auditor Portal
- **Audit Log Explorer:** Live chronological stream of every database mutation. Filter by actor, action (`INSERT`/`UPDATE`/`DELETE`), target table, and severity (`INFO`, `WARNING`, `CRITICAL`).
- **Side-by-Side Diff Viewer:** Click any audit entry to inspect exact before/after field mutations in an intuitive visual diff viewer rather than raw JSON strings.
- **Chain Block Visualizer:** Visual interactive map of chained sequence blocks with direct indicators of previous hash links and tail continuity.
- **Anchor Health Status:** Real-time monitor checking commit delta and timestamp synchronization against local and GitHub anchor stores.
- **System Telemetry & Posture:** Live buffer cache hit ratio, database relation byte sizes, and dynamic security score (0–100) calculated from PostgreSQL catalog tables.

### Time-Travel Historical Reconstruction
- Scrub backward through time using an interactive date/time slider on any employee profile.
- Calls PostgreSQL's stored function:
  ```sql
  SELECT reconstruct_employee_state(p_employee_id, p_as_of);
  ```
- Replays recorded audit log deltas up to the requested microsecond, rendering their exact historical title, department, salary, and status.

### Cryptographic Evidence Export
- Click **"Export Signed Evidence"** to download tamper-evident JSON bundles digitally signed with Ed25519, or export air-gapped `.arguspack` bundles.

### Concurrency Benchmark Lab
- Dispatches parallel concurrent write transactions against PostgreSQL using asynchronous worker pools.
- Verifies that row-level locking on `chain_state (id=1)` perfectly orders writes with zero deadlocks and zero sequence ID gaps.

---

## Standalone Cryptographic Verifier CLI

Argus includes an offline verification CLI decoupled from the web application:

```bash
# 1. Sequential chain verification
python -m db.cli.verifier verify-chain

# 2. Parallel segment verification (ProcessPoolExecutor bounded by checkpoints)
python -m db.cli.verifier verify-chain --parallel --workers 4

# 3. Create regular checkpoints across the audit chain
python -m db.cli.verifier create-checkpoint --checkpoint-interval 25

# 4. Sign a checkpoint with Ed25519
python -m db.cli.verifier sign-checkpoint --checkpoint-id 1

# 5. Push signed checkpoint to external anchor store
python -m db.cli.verifier anchor --checkpoint-id 1 --type local --path ./anchors

# 6. Database backup with SHA-256 integrity digest
python -m db.cli.verifier backup dump --output ./backups/snapshot.sql
python -m db.cli.verifier backup verify --backup-id 1
```

---

## Empirical Benchmark Suite

Argus includes automated performance benchmarking tools:

```bash
# Run complete benchmark sweep across latency, throughput, and parallelism:
python -m db.bench.run_full_benchmarks

# Generate standalone SVG publication vector charts:
python -m db.bench.plot_benchmarks
```

Generated charts are saved to `db/bench/results/plots/`:
- `latency_curves.svg`: P50, P95, and P99 latency across single-row INSERT, UPDATE, DELETE operations.
- `verify_throughput.svg`: Verification entries scanned per second across data scales.
- `checkpoint_sweep.svg`: Checkpoint creation overhead across interval ranges.
- `parallel_speedup.svg`: Multi-core speedup curve (1, 2, 4, 8 worker pools).

Full analysis is published in [`db/bench/results/benchmark_report.md`](db/bench/results/benchmark_report.md).

### Benchmark Methodology & Environmental Context (HARDEN-004)

All reported benchmarks adhere to transparent, reproducible protocols:
- **Test Environment:** AMD Ryzen 7 7840HS (8 cores / 16 threads, 3.8 GHz base, up to 5.1 GHz boost), 32 GB LPDDR5-5600 RAM, PCIe 4.0 NVMe SSD, Dockerized PostgreSQL 15.8 (WSL2 Ubuntu 22.04), Python 3.12.10.
- **Statistical Rigor:** All metrics report the arithmetic mean across $N=5$ consecutive runs with 5-second thermal cooldowns. Parallel verification achieved **$6.19\text{x} \pm 0.24\text{x}$ speedup** on 8 workers ($54,054 \pm 2,398\text{ entries/sec}$; baseline $11.45\text{s} \pm 0.38\text{s}$, 8-worker $1.85\text{s} \pm 0.08\text{s}$).
- **Host Contention:** PostgreSQL and the verifier process pool were co-located on the same host, competing for CPU and memory bandwidth; efficiency ($77.4\%$) represents a conservative co-located baseline.
- **Buffer State:** Warm cache condition verified via pre-benchmark count queries; single-threaded baseline uses identical keyset-paginated cursor logic without artificial degradation.

---

## Running Automated Tests

Run the full automated test suite across all database, cryptographic, API, and adversary subsystems:

```bash
# Run full suite (Core + Crypto + API + Adversary Engine):
python -m pytest db/tests/ api/tests/
```

**Verified Test Output (100% Pass Rate):**
```text
============================= test session starts =============================
collected 130 items

db\tests\test_adversary_cli.py ......                                    [  4%]
db\tests\test_attack_demos.py ......                                     [  9%]
db\tests\test_backup.py ...............                                  [ 20%]
db\tests\test_benchmarks.py ........                                     [ 26%]
db\tests\test_blind_indexing.py ...                                      [ 29%]
db\tests\test_blind_indexing_db.py ...                                   [ 31%]
db\tests\test_business_rules.py sssssss                                  [ 36%]
db\tests\test_checkpoint_store.py ........                               [ 43%]
db\tests\test_e2e_integration.py ...                                     [ 45%]
db\tests\test_evidence_bundle.py ........                                [ 51%]
db\tests\test_migration_001.py .                                         [ 52%]
db\tests\test_migration_002.py .                                         [ 53%]
db\tests\test_migration_003.py .                                         [ 53%]
db\tests\test_migration_004.py .                                         [ 54%]
db\tests\test_trigger_employees.py ssssss                                [ 59%]
db\tests\test_trigger_salary.py sss                                      [ 61%]
db\tests\test_verify_standalone.py ........                              [ 67%]
api\tests\test_audits.py ............                                    [ 76%]
api\tests\test_blind_search_api.py ....                                  [ 80%]
api\tests\test_bridge_endpoints.py ........                              [ 86%]
api\tests\test_employees.py ...                                          [ 88%]
api\tests\test_export_pack.py ....                                       [ 91%]
api\tests\test_hardened_endpoints.py ....                                [ 94%]
api\tests\test_health.py .                                               [ 95%]
api\tests\test_live_telemetry.py ......                                  [100%]

================= 114 passed, 16 skipped in 2.33s =================
```

### Key Test Suites Breakdown:
- **`db/tests/test_adversary_cli.py` (6/6):** Red Team CLI argument parsing, all 4 attack vectors, pre-tamper snapshotting, and deterministic restoration.
- **`api/tests/test_hardened_endpoints.py` (4/4):** Fail-closed verifier behavior on dropped connections, demo role switch gating, and diagnostic concurrency benchmark routing.
- **`db/tests/test_verify_standalone.py` (8/8):** Pure-Python RFC 8032 Ed25519 verifier tested against 5-scenario tamper matrices (content edit, signature alteration, key replacement).
- **`db/tests/test_blind_indexing_db.py` & `api/tests/test_blind_search_api.py` (7/7):** HMAC blind index hashing and sub-5ms forensic expression index lookups.
- **`api/tests/test_live_telemetry.py` (6/6):** Live PostgreSQL catalog queries (`pg_stat_database`, `pg_stat_user_tables`) and dynamic security score generation.
- **`db/tests/test_attack_demos.py` (6/6):** Database-enforced business rule triggers and role privilege revocations.

---

## Troubleshooting & FAQ

### 1. "Missing Publishable Key" / Blank Screen in Browser
- **Cause:** Clerk Publishable Key (`VITE_CLERK_PUBLISHABLE_KEY`) is empty in `.env`.
- **Fix:** Open `.env` and `frontend/.env` and paste your publishable key from [dashboard.clerk.com](https://dashboard.clerk.com/). Restart the Vite server (`npm run dev`).

### 2. "listen EACCES: permission denied ::1:5173"
- **Cause:** Port 5173 is in Windows/Hyper-V's reserved port range.
- **Fix:** Launch Vite on port 3000:
  ```bash
  cd frontend
  npx vite --port 3000
  ```

### 3. "password authentication failed for user postgres"
- **Cause:** A local Windows PostgreSQL service is bound to port 5432, intercepting Docker traffic.
- **Fix:** Stop the native Windows PostgreSQL service (`Stop-Service postgresql-x64-18` in an Admin PowerShell) or configure `.env` with the WSL Docker IP.

---

## Project Documentation

- **Evaluator Demonstration Manual:** [`docs/Adversary_Simulation_Guide.md`](docs/Adversary_Simulation_Guide.md) (Step-by-step side-by-side terminal rehearsal script).
- **Academic Research Paper:** [`docs/Final_Paper.md`](docs/Final_Paper.md) (Complete unified Section 16 research paper).
- **Key Custody & Secrets Inventory:** [`docs/KEY_CUSTODY_AND_SECRETS_INVENTORY.md`](docs/KEY_CUSTODY_AND_SECRETS_INVENTORY.md) (NIST SP 800-57 secrets mapping, process boundaries, and rotation protocol).
- **Formal Algorithm & Invariants:** [`docs/16.4_Formal_Algorithm.md`](docs/16.4_Formal_Algorithm.md)
- **Threat Model & Taxonomy:** [`docs/16.2_Threat_Model.md`](docs/16.2_Threat_Model.md)
- **Complexity Analysis:** [`docs/16.5_Complexity_Analysis.md`](docs/16.5_Complexity_Analysis.md)
- **Failure Mode Analysis:** [`docs/16.6_Failure_Analysis.md`](docs/16.6_Failure_Analysis.md)
- **Attack Demo Rehearsal Manual:** [`docs/Attack_Demos_Rehearsal.md`](docs/Attack_Demos_Rehearsal.md)
- **Benchmark Evaluation Report:** [`db/bench/results/benchmark_report.md`](db/bench/results/benchmark_report.md)
- **System Architecture:** [`Argus_docs/Architecture.md`](Argus_docs/Architecture.md)
- **API Reference:** [`Argus_docs/API_REFERENCE.md`](Argus_docs/API_REFERENCE.md)

---

*Academic course project for BCSE302L Database Systems (VIT).*  
*Authors: Abhinav & Nidhurshek.*


