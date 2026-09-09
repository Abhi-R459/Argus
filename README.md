# Argus

> **A tamper-evident, self-verifying audit trail engine for PostgreSQL**, demonstrated through an Employee Records application.  
> *Course Project for BCSE302L Database Systems — Abhinav & Nidhurshek.*

---

## Table of Contents

- [Overview](#overview)
- [Architecture & Security Model](#architecture--security-model)
- [Technology Stack](#technology-stack)
- [Prerequisites](#prerequisites)
- [First-Time Setup Guide (Detailed)](#first-time-setup-guide-detailed)
  - [Step 1: Clone Repository & Switch Branch](#step-1-clone-repository--switch-branch)
  - [Step 2: Environment Configuration (`.env`)](#step-2-environment-configuration-env)
  - [Step 3: Database Setup with Docker](#step-3-database-setup-with-docker)
  - [Step 4: Database Roles & Migrations](#step-4-database-roles--migrations)
  - [Step 5: Backend Setup (FastAPI)](#step-5-backend-setup-fastapi)
  - [Step 6: Frontend Setup (React + Vite)](#step-6-frontend-setup-react--vite)
- [Running via Docker Compose (All-in-One)](#running-via-docker-compose-all-in-one)
- [Running the Cryptographic Verifier CLI](#running-the-cryptographic-verifier-cli)
- [Running Automated Tests](#running-automated-tests)
- [Troubleshooting Common Issues](#troubleshooting-common-issues)
- [Project Documentation](#project-documentation)

---

## Overview

Traditional audit logs are stored in standard database tables where privileged users (including administrators being audited) can silently alter or delete records without detection.

**Argus solves this natively within PostgreSQL:**
- **Trigger-Based Hash Chaining**: Every `INSERT`, `UPDATE`, or `DELETE` on monitored tables is captured by an `AFTER` trigger into an append-only `audit_log`. Each record contains a cryptographic SHA-256 digest linking it directly to the hash of the preceding entry.
- **Tamper Evidence**: Modifying, deleting, or reordering any historical audit entry invalidates the cryptographic hash chain for all subsequent entries.
- **Role-Based Privilege Separation**:
  - `hr_admin`: Can manage employees and salaries; read-only access to audit logs; strictly prohibited from updating or deleting audit logs.
  - `compliance_auditor`: Read-only access to audit chains, checkpoints, and views; cannot access raw PII or modify employee records.
- **Signed Checkpoints & Anchoring**: Periodic snapshots of the chain tail are cryptographically signed using Ed25519 keys and anchored outside the database.

---

## Architecture & Security Model

```
 ┌────────────────────────────────────────────────────────┐
 │                      Client / UI                       │
 │      React 19 + Vite + Tailwind CSS + Clerk Auth       │
 └───────────────────────────┬────────────────────────────┘
                             │ HTTP / JSON
                             ▼
 ┌────────────────────────────────────────────────────────┐
 │                   FastAPI Backend                      │
 │   - JWT Verification (Clerk Middleware)               │
 │   - Least-Privilege Session Routing (RBAC)            │
 └─────────────┬────────────────────────────┬─────────────┘
               │ hr_admin pool              │ compliance_auditor pool
               ▼                            ▼
 ┌────────────────────────────────────────────────────────┐
 │                  PostgreSQL 15+                        │
 │  ┌────────────────────────┐  ┌──────────────────────┐  │
 │  │      Entity Tables     │  │   Audit Trail Engine │  │
 │  │  departments, roles,   │  │  audit_log (chained) │  │
 │  │  employees, salary_hist│  │  chain_state, flags  │  │
 │  └───────────┬────────────┘  └──────────▲───────────┘  │
 │              │   AFTER Trigger Hook     │              │
 │              └──────────────────────────┘              │
 └────────────────────────────────────────────────────────┘
```

---

## Technology Stack

| Layer | Technologies |
|---|---|
| **Frontend** | React 19, Vite, Tailwind CSS, TanStack React Query, React Hook Form, Zod, Lucide React |
| **Authentication** | Clerk Auth (Hobby Tier) |
| **Backend API** | FastAPI, SQLAlchemy 2 (asyncpg), Pydantic v2, Uvicorn |
| **Database** | PostgreSQL 15+, `pgcrypto`, PL/pgSQL triggers, views, stored procedures |
| **Verification & Crypto** | Standalone Python CLI, Ed25519 signatures (`cryptography`), SHA-256 |
| **Migrations** | Alembic |
| **Containerization** | Docker, Docker Compose |

---

## Prerequisites

Before starting, make sure the following software is installed on your machine:

1. **Git** (v2.30+)
2. **Python** (v3.11 or v3.12)
3. **Node.js** (v18+ or v20+) & **npm** (v9+)
4. **Docker Desktop** (running and configured for Linux containers / WSL2 on Windows)
5. **A free Clerk account**: [clerk.com](https://clerk.com/) to obtain API keys (`pk_test_...` and `sk_test_...`)

---

## First-Time Setup Guide (Detailed)

Follow these steps in order if you have just cloned the repository:

### Step 1: Clone Repository & Switch Branch

```bash
git clone https://github.com/Abhi-R459/Argus.git
cd Argus

# Switch to the development integration branch
git checkout dev
git pull origin dev
```

---

### Step 2: Environment Configuration (`.env`)

Create your local environment file by copying the template:

```bash
# Windows (PowerShell)
Copy-Item .env.example .env

# macOS / Linux
cp .env.example .env
```

Open `.env` in your code editor and configure your secrets:

```env
# Database Connections
DATABASE_URL_MIGRATIONS=postgresql://postgres:password@localhost:5432/argus
DATABASE_URL_HR_ADMIN=postgresql+asyncpg://hr_admin:password@localhost:5432/argus
DATABASE_URL_COMPLIANCE_AUDITOR=postgresql+asyncpg://compliance_auditor:password@localhost:5432/argus

# Clerk Authentication Keys (From https://dashboard.clerk.com/ -> API Keys)
VITE_CLERK_PUBLISHABLE_KEY=pk_test_your_clerk_publishable_key_here
CLERK_SECRET_KEY=sk_test_your_clerk_secret_key_here
CLERK_JWT_KEY=
CLERK_WEBHOOK_SIGNING_SECRET=

# Cryptographic Verifier & Anchor Settings
SIGNING_PRIVATE_KEY_PATH=./keys/verifier_private_key.pem
ANCHOR_STORE=local_file
ANCHOR_FILE_PATH=./anchor/chain_anchor.log
GITHUB_ANCHOR_REPOSITORY=
GITHUB_ANCHOR_TOKEN=
CHECKPOINT_INTERVAL=25
```

> [!IMPORTANT]
> - **Publishable Key (`VITE_CLERK_PUBLISHABLE_KEY`)** must start with `pk_test_...`.
> - **Secret Key (`CLERK_SECRET_KEY`)** must start with `sk_test_...`.
> - The async database connection strings (`DATABASE_URL_HR_ADMIN` and `DATABASE_URL_COMPLIANCE_AUDITOR`) **must** use the `postgresql+asyncpg://` scheme.

---

### Step 3: Database Setup with Docker

Start the PostgreSQL 15 container in the background using Docker Compose:

```bash
docker compose up -d db
```

Verify that the database container is healthy:

```bash
docker ps --filter "name=argus-postgres"
```

You should see `argus-postgres` running on port `5432->5432/tcp` with status `healthy`.

---

### Step 4: Database Roles & Migrations

The database requires initialization of least-privilege roles and schema migration tables:

1. **Initialize Application Roles (`hr_admin` and `compliance_auditor`):**

   ```bash
   # Windows (PowerShell)
   Get-Content db/scripts/setup_roles.sql | docker exec -i argus-postgres psql -U postgres -d argus

   # macOS / Linux
   docker exec -i argus-postgres psql -U postgres -d argus < db/scripts/setup_roles.sql
   ```

2. **Sync Role Passwords:**

   Ensure the role passwords match your connection string in `.env`:

   ```bash
   docker exec -i argus-postgres psql -U postgres -d argus -c "ALTER ROLE hr_admin WITH PASSWORD 'password'; ALTER ROLE compliance_auditor WITH PASSWORD 'password';"
   ```

3. **Run Alembic Migrations:**

   Apply all schema migrations (tables, audit triggers, business rules, and views):

   ```bash
   alembic upgrade head
   ```

4. **Re-apply Role Permissions:**

   Now that the tables exist, execute the permission grants:

   ```bash
   # Windows (PowerShell)
   Get-Content db/scripts/setup_roles.sql | docker exec -i argus-postgres psql -U postgres -d argus

   # macOS / Linux
   docker exec -i argus-postgres psql -U postgres -d argus < db/scripts/setup_roles.sql
   ```

---

### Step 5: Backend Setup (FastAPI)

1. **Set up a Python virtual environment:**

   ```bash
   # In the root repository directory
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
   uvicorn api.main:app --reload --port 8000
   ```

4. **Verify Backend Health:**
   - Open your browser to: [http://localhost:8000/api/health](http://localhost:8000/api/health) (should respond `{"status":"ok"}`).
   - Explore interactive Swagger API docs: [http://localhost:8000/docs](http://localhost:8000/docs).

---

### Step 6: Frontend Setup (React + Vite)

Open a **new terminal** window:

1. **Navigate to the frontend directory:**

   ```bash
   cd frontend
   ```

2. **Install Node dependencies:**

   ```bash
   npm install --legacy-peer-deps
   ```

   > [!TIP]
   > The `--legacy-peer-deps` flag is required to allow `lucide-react` icons to resolve smoothly with React 19.

3. **Start the Vite dev server:**

   ```bash
   npm run dev
   ```

   *(Or if port 5173 is reserved by your operating system/Hyper-V, run: `npx vite --port 3000`)*

4. **Open the App in your Browser:**
   - Visit: **[http://localhost:5173](http://localhost:5173)** (or `http://localhost:3000`)
   - You will see the **Argus Audit Engine** authentication portal powered by Clerk.
   - Sign in using your Clerk credentials to view the **HR Admin** or **Compliance Auditor** dashboard.

---

## Running via Docker Compose (All-in-One)

If you prefer to containerize all three tiers (Database, Backend API, and Frontend) simultaneously:

```bash
# Ensure .env is populated with your Clerk keys
docker compose up --build
```

- **Frontend:** [http://localhost:80](http://localhost:80)
- **Backend API:** [http://localhost:8000](http://localhost:8000)
- **Interactive Docs:** [http://localhost:8000/docs](http://localhost:8000/docs)
- **Database:** `localhost:5432`

---

## Running the Cryptographic Verifier CLI

Argus includes an independent verifier engine that walks the audit log, re-calculates each SHA-256 hash using the stored inputs, validates sequential linkage, and checks signed checkpoints:

```bash
# Sequential chain verification
python -m db.cli.verifier --verify

# Checkpoint-parallelized verification
python -m db.cli.verifier --verify --parallel

# Verify against external anchor file
python -m db.cli.verifier --verify --anchor ./anchor/chain_anchor.log
```

---

## Running Automated Tests

### 1. Backend API Tests (FastAPI & Schemas)
```bash
python -m pytest api/tests
```

### 2. Database Core & Security Tests (Triggers, Hashes, Business Rules)
```bash
python -m pytest db/tests
```

### 3. Frontend End-to-End Tests (Playwright)
```bash
cd frontend
npx playwright test
```

### 4. Concurrency & Benchmark Testing
```bash
python -m db.bench.pilot_benchmark
```

---

## Troubleshooting Common Issues

### 1. "Missing Publishable Key" / Blank Screen in Browser
- **Cause**: Clerk Publishable Key (`VITE_CLERK_PUBLISHABLE_KEY`) is missing or empty in `.env`.
- **Fix**: Open `.env` and verify `VITE_CLERK_PUBLISHABLE_KEY=pk_test_...` is set with your actual key from [dashboard.clerk.com](https://dashboard.clerk.com/). Restart the Vite server after modifying `.env`.

### 2. "The publishableKey passed to Clerk is invalid"
- **Cause**: You pasted a Secret Key (`sk_test_...`) instead of a Publishable Key (`pk_test_...`).
- **Fix**: Check `.env` and ensure `VITE_CLERK_PUBLISHABLE_KEY` starts with `pk_test_` and `CLERK_SECRET_KEY` starts with `sk_test_`.

### 3. "Error: listen EACCES: permission denied ::1:5173"
- **Cause**: Port 5173 is in Windows or Hyper-V's excluded port range.
- **Fix**: Run the frontend on port 3000:
  ```bash
  cd frontend
  npx vite --port 3000
  ```

### 4. "password authentication failed for user postgres"
- **Cause**: A native PostgreSQL instance installed on Windows is squatting on port 5432, intercepting Docker traffic.
- **Fix**: Connect using the Docker WSL IP (e.g., `172.27.x.x:5432`) in `.env`, or stop the native Windows PostgreSQL service (`Stop-Service postgresql-x64-18` in an Admin terminal).

---

## Project Documentation

Detailed design specifications, contracts, and course deliverables:

- **[Product Requirements Document](Argus_docs/PRD_Argus.md)**: Full requirements, threat models, and curriculum mapping.
- **[System Architecture](Argus_docs/Architecture.md)**: Relational schema, ER diagram, and cryptographic chaining mechanics.
- **[Frontend Architecture](Argus_docs/FRONTEND_ARCHITECTURE.md)**: Component tree, state management, and dashboard design.
- **[API Reference](Argus_docs/API_REFERENCE.md)**: Endpoint documentation and JSON contract specifications.
- **[Development Plan & Timeline](Argus_docs/Argus_Team_Development_Plan.md)**: Milestone breakdown and team division.

---

*Academic course project for BCSE302L Database Systems (VIT).*  
*Authors: Abhinav & Nidhurshek.*
