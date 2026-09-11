# Argus

> **A tamper-evident, self-verifying audit trail engine for PostgreSQL**, demonstrated through an enterprise Employee Records management system.  
> *Course Project for BCSE302L Database Systems — Abhinav & Nidhurshek.*

[![Tests](https://img.shields.io/badge/tests-60%20passed-brightgreen.svg)](#running-automated-tests)
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
- [Application Walkthrough & Features](#application-walkthrough--features)
  - [HR Admin Portal](#hr-admin-portal)
  - [Compliance Auditor Portal](#compliance-auditor-portal)
  - [Time-Travel Historical Reconstruction](#time-travel-historical-reconstruction)
  - [Cryptographic Evidence Export](#cryptographic-evidence-export)
  - [Concurrency Attack Lab](#concurrency-attack-lab)
- [Standalone Cryptographic Verifier CLI](#standalone-cryptographic-verifier-cli)
- [Attack Demonstrations & Defense Rehearsal](#attack-demonstrations--defense-rehearsal)
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
  - `hr_admin`: Manages employees and compensation; read-only to audit logs; strictly denied `UPDATE` or `DELETE` privileges on audit logs.
  - `compliance_auditor`: Read-only access to audit logs, views, and integrity verification; denied write access and raw PII access.
- **Zero-Gap Concurrency Guarantee**: Row-level locking on `chain_state` serializes concurrent transactions without deadlocks, ensuring zero sequence ID gaps.
- **Ed25519 Checkpoint Signing & Multi-Target Anchoring**: Snapshots of the chain tail are cryptographically signed with Ed25519 keys and anchored outside the database (local disk or GitHub repository).

---

## Key Features

| Capability | Description |
|---|---|
| 🔗 **Cryptographic Chaining** | In-engine SHA-256 digest linking every state change to the prior audit block. |
| 🛡️ **Business Rule Triggers** | Database-level blocks against salary reductions $> 30\%$, self-salary modification, and SSN alterations. |
| 🕵️ **PII Masking & Encryption** | Automatic database-level masking of sensitive credentials and `pgcrypto` field-level encryption. |
| ⚡ **Parallel Verifier** | Standalone verification engine dividing the chain into checkpoint-bounded segments for concurrent verification. |
| ⏳ **Time-Travel Querying** | Replays historical `audit_log` deltas to reconstruct any employee's state as of an exact microsecond. |
| 📜 **Signed Evidence Export** | Generates tamper-evident JSON bundles digitally signed with Ed25519 for external compliance audits. |
| 🧪 **Interactive Concurrency Lab** | Built-in UI to trigger parallel write races, demonstrating lock serialization and tamper detection live. |

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

## Application Walkthrough & Features

### HR Admin Portal
- **Employee Directory Table:** Search, filter by department, paginate, and sort employees.
- **Create & Edit Employee:** Validated modals capturing employee profile details. Sensitive fields (`national_id`, `contact_info`) are encrypted with `pgcrypto` at the database level.
- **Salary Adjustments:** Dedicated modal enforcing business constraints (e.g. raises and $< 30\%$ adjustments allowed, self-modifications blocked).

### Compliance Auditor Portal
- **Audit Log Explorer:** Live chronological stream of every database mutation. Filter by actor, action (`INSERT`/`UPDATE`/`DELETE`), target table, and severity (`INFO`, `WARNING`, `CRITICAL`).
- **Side-by-Side Diff Viewer:** Click any audit entry to inspect exact before/after field mutations in an intuitive visual diff viewer rather than raw JSON strings.
- **Chain Block Visualizer:** Visual interactive map of chained sequence blocks with direct indicators of previous hash links and tail continuity.

### Time-Travel Historical Reconstruction
- Scrub backward through time using an interactive date/time slider on any employee profile.
- Calls PostgreSQL's stored function:
  ```sql
  SELECT reconstruct_employee_state(p_employee_id, p_as_of);
  ```
- Replays recorded audit log deltas up to the requested microsecond, rendering their exact historical title, department, salary, and status.

### Cryptographic Evidence Export
- Click **"Export Signed Evidence"** to trigger `GET /api/audit-logs/export`.
- Returns a downloadable JSON package containing all chronological audit entries, a canonical SHA-256 payload digest, and an **Ed25519 digital signature** generated from the offline verification key.

### Concurrency Attack Lab
- Dedicated test interface allowing auditors to dispatch parallel concurrent write transactions against identical records.
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

## Attack Demonstrations & Defense Rehearsal

Argus includes comprehensive attack demonstrations showing how it defeats common administrative bypasses. Complete live demonstration scripts and `psql` snippets are detailed in [`docs/Attack_Demos_Rehearsal.md`](docs/Attack_Demos_Rehearsal.md):

| Demo # | Attack Vector | Argus Defense Mechanism |
|---|---|---|
| **Demo 1** | HR Admin attempts `DELETE FROM audit_log;` | `42501` Permission Denied — role privileges strictly revoked. |
| **Demo 2** | Superuser bypasses triggers to modify historical salary | Standalone verifier catches hash mismatch at tampered sequence ID. |
| **Demo 3** | User drops salary by $40\%$ | Trigger `chk_salary_decrease_threshold` raises exception and aborts transaction. |
| **Demo 4** | HR Admin modifies their own salary record | Trigger `chk_prevent_self_salary_modification` blocks transaction. |
| **Demo 5** | Malicious DBA deletes rows from `chain_checkpoints` | Verifier detects sequence gap and checkpoint mismatch against external anchor. |
| **Demo 6** | Attacker injects forged signature into external anchor | Public key verification rejects forged Ed25519 signature. |

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

---

## Running Automated Tests

Run the full automated test suite across all subsystems:

```bash
# Run full suite (Core + Crypto + API):
python -m pytest db/tests/ api/tests/ -v
```

Output:
```
db/tests/test_attack_demos.py ......                                     [  7%]
db/tests/test_backup.py ...............                                  [ 27%]
db/tests/test_benchmarks.py ........                                     [ 38%]
db/tests/test_checkpoint_store.py ........                               [ 57%]
db/tests/test_e2e_integration.py ...                                     [ 61%]
db/tests/test_migration_001.py .                                         [ 63%]
db/tests/test_migration_002.py .                                         [ 64%]
db/tests/test_migration_003.py .                                         [ 65%]
db/tests/test_migration_004.py .                                         [ 67%]
api/tests/test_audits.py ............                                    [ 94%]
api/tests/test_employees.py ...                                          [ 98%]
api/tests/test_health.py .                                               [100%]

================= 60 passed, 16 skipped in 2.35s ==================
```

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

- **Academic Research Paper:** [`docs/Final_Paper.md`](docs/Final_Paper.md) (Complete unified Section 16 research paper).
- **Formal Algorithm & Invariants:** [`docs/16.4_Formal_Algorithm.md`](docs/16.4_Formal_Algorithm.md)
- **Threat Model & Taxonomy:** [`docs/16.2_Threat_Model.md`](docs/16.2_Threat_Model.md)
- **Complexity Analysis:** [`docs/16.5_Complexity_Analysis.md`](docs/16.5_Complexity_Analysis.md)
- **Attack Demo Rehearsal Manual:** [`docs/Attack_Demos_Rehearsal.md`](docs/Attack_Demos_Rehearsal.md)
- **Benchmark Evaluation Report:** [`db/bench/results/benchmark_report.md`](db/bench/results/benchmark_report.md)
- **System Architecture:** [`Argus_docs/Architecture.md`](Argus_docs/Architecture.md)
- **API Reference:** [`Argus_docs/API_REFERENCE.md`](Argus_docs/API_REFERENCE.md)

---

*Academic course project for BCSE302L Database Systems (VIT).*  
*Authors: Abhinav & Nidhurshek.*

