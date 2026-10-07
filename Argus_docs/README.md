# Argus

> **Historical team handoff guide.** Some routes, hosting references, and setup
> details below predate the current implementation. For the current local
> walkthrough and safe demo seeding, use the root [README](../README.md),
> [Local Professor Demo Setup](../docs/LOCAL_DEMO_SETUP.md), and
> [Conference Positioning and Professor Walkthrough](../docs/CONFERENCE_AND_DEMO_GUIDE.md).
> For current API behavior, use [API Reference](API_REFERENCE.md).

**A tamper-evident, self-verifying audit trail engine for PostgreSQL.**

BCSE302L Database Systems — course project by Abhinav & Nidhurshek

---

## Table of Contents

- [Project Description](#project-description)
- [Technology Stack](#technology-stack)
- [Project Structure](#project-structure)
- [Installation](#installation)
- [Execution](#execution)
- [Backup and Restore Demonstration](#backup-and-restore-demonstration)
- [Delivery Evidence](#delivery-evidence)
- [Documentation](#documentation)
- [Team](#team)

---

## Project Description

Most systems that claim to keep an "audit log" are really just storing that log in an ordinary database table — one that anyone with sufficient privilege, including the database administrator being watched, can quietly edit or delete. PostgreSQL itself has no built-in way to prevent this; even Amazon discontinued its own managed solution to this exact problem (QLDB) in 2025.

**Argus is a PostgreSQL tamper-evidence prototype.** Monitored row changes are captured by `AFTER` triggers in a hash-linked audit log, and the standalone verifier checks the chain and available checkpoint evidence. External anchoring depends on the configured provider; a local file is not an independent trust domain. The HR-only on-demand checkpoint action uses a local key in development/demo and is disabled in production until managed signing is integrated. The standalone verifier remains a separate process, but the demo signing route does not provide an independent signer boundary.

Two application roles sit on top of this: an **HR Admin** who manages employee records (the "watched" role), and a **Compliance Auditor** who can only read the audit trail and run verification (the "watching" role). Clerk supplies secure authentication; Argus keeps the course-required local `users` table with a `role` column and maps the verified Clerk user to real PostgreSQL roles with `GRANT`/`REVOKE` privilege separation.

Full requirements, threat model, and research framing live in [`PRD_Argus.md`](./PRD_Argus.md); the technical design lives in [`Architecture.md`](./Architecture.md).

---

## Technology Stack

| Layer | Technology |
|---|---|
| Frontend | React + Vite, Tailwind CSS, Clerk React, React Hook Form, Zod, TanStack Query |
| Backend | FastAPI (Python), SQLAlchemy 2 (async), Pydantic |
| Database | PostgreSQL 15+ — `pgcrypto`, `JSONB`, `AFTER` triggers, B-tree indexes, `FOR UPDATE` row-level locking |
| Verification | Standalone Python CLI, `cryptography` (Ed25519), independent database credentials |
| Migrations | Alembic |
| Auth | Clerk Hobby: prebuilt login/logout, OAuth, managed sessions; local `users.role` authorizes Argus access |
| Containerization | Docker Compose |
| Deployment | Earlier free-tier target plan only; the verified walkthrough runs locally with Docker Compose and Clerk Development. See the root `docs/LOCAL_DEMO_SETUP.md`. |
| External anchor | Pluggable: Local File, GitHub repository, RFC 3161 TSA (.tsr), and AWS S3 Object Lock (COMPLIANCE WORM) |

**ORM boundary, briefly:** standard CRUD, local user/RBAC lookups, and dashboard reads go through SQLAlchemy. Raw SQL/PL-pgSQL is used only where the course rubric explicitly allows it — triggers, locking, the time-travel function, the suspicious-activity procedure, and the verifier's chain walk.

---

## Project Structure

```
argus/
├── db/              # Schema, Alembic migrations, PL/pgSQL triggers,
│                    # verifier CLI, benchmark scripts        (owner: Abhinav)
├── api/             # FastAPI app — auth, endpoints           (owner: Nidhurshek)
├── frontend/        # React app — HR Admin & Compliance
│                    # Auditor dashboards                      (owner: Nidhurshek)
├── contracts/       # Schema reference, OpenAPI spec — frozen
│                    # after Week 1                              (shared)
├── .env.example     # Safe environment-variable names only
├── .gitignore
├── docker-compose.yml
├── PRD_Argus.md
├── Architecture.md
├── Argus_Team_Development_Plan.md
└── README.md
```

---

## Installation

### Prerequisites
- Python 3.11+
- Node.js 18+
- PostgreSQL 15+ locally through Docker (required for the real superuser attack demo)
- Clerk application configured with development and production keys
- Neon project for the free deployed PostgreSQL database
- Docker & Docker Compose (optional, for containerized setup)

### 1. Clone the repository
```bash
git clone <repository-url>
cd argus
```

### 2. Backend setup
```bash
cd api
python -m venv venv
source venv/bin/activate      # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 3. Configure environment variables
Copy `.env.example` to `api/.env` and fill it locally. Never commit this file:
```env
DATABASE_URL_MIGRATIONS=postgresql://postgres:<password>@localhost:5432/argus
DATABASE_URL_HR_ADMIN=postgresql://hr_admin:<password>@localhost:5432/argus
DATABASE_URL_COMPLIANCE_AUDITOR=postgresql://compliance_auditor:<password>@localhost:5432/argus
VITE_CLERK_PUBLISHABLE_KEY=<Clerk frontend key>
CLERK_SECRET_KEY=<Clerk backend key>
CLERK_JWT_KEY=<Clerk JWT public key>
CLERK_WEBHOOK_SIGNING_SECRET=<optional Clerk webhook secret>
SIGNING_PRIVATE_KEY_PATH=./keys/verifier_private_key.pem
ANCHOR_STORE=local_file
ANCHOR_FILE_PATH=./anchor/chain_anchor.log
GITHUB_ANCHOR_REPOSITORY=<owner/private-anchor-repo>
GITHUB_ANCHOR_TOKEN=<fine-grained token, deployed verifier only>
CHECKPOINT_INTERVAL=25
```

### 4. Set up the database
```bash
# Create the database and the two application roles (hr_admin, compliance_auditor)
# — see db/setup_roles.sql for exact GRANT/REVOKE statements
psql -U postgres -f db/setup_roles.sql

# Run migrations (creates all tables, views, trigger functions, a function, and a real stored procedure)
cd api
alembic upgrade head
```

### 5. Frontend setup
```bash
cd frontend
npm install
```

---

## Execution

### Running locally (development mode)
```bash
# Terminal 1 — backend
cd api
uvicorn main:app --reload

# Terminal 2 — frontend
cd frontend
npm run dev
```
Visit `http://localhost:5173`. Sign in through Clerk, then use a seeded local `users` row mapped to the Clerk user as `hr_admin` or `compliance_auditor`.

### Running via Docker Compose
```bash
docker compose up --build
```
This starts `postgres`, `api`, and `frontend` as separate services, matching the deployment architecture described in `Architecture.md`.

### Running the verifier and adversary engines
The verifier and adversary simulator are intentionally standalone processes decoupled from the web app:

```bash
# Interactive Terminal User Interfaces (TUI):
python -m db.cli.tui                 # Master launcher
python -m db.cli.verifier --tui       # Verifier TUI
python -m db.cli.adversary --tui      # Adversary TUI

# Command-Line Interface (CLI):
python -m db.cli.verifier verify-chain                 # Walk the chain, report status
python -m db.cli.verifier verify-chain --parallel --workers 4  # Parallelized verification
python -m db.cli.adversary status                      # Active attack diagnostics
python -m db.cli.adversary heal                        # Restore pristine state
```

### Running the benchmark harness
```bash
cd db
python benchmark.py --sizes 100,1000,10000,100000
```

---

## Backup and Restore Demonstration

The course-required recovery demonstration uses PostgreSQL's native tools. Create the backup outside the repository, hash it, and record the hash in the `backups` table before restoration:

```bash
pg_dump -Fc -d argus -f ../backups/argus_before_restore.dump
pg_restore --clean --if-exists -d argus_restore_test ../backups/argus_before_restore.dump
```

For the final submission, include the command output and a screenshot of a successful restore. Do not commit database dumps containing employee data.

---

## Delivery Evidence

- Private GitHub repository with both team members as collaborators
- `main`, `dev`, and personal feature branches; at least 10 meaningful commits and pull requests into `dev`
- Dockerfiles, `docker-compose.yml`, and Docker Hub image link(s)
- Live frontend URL, FastAPI URL, and deployed Neon database configuration recorded privately
- `.gitignore` committed before source code; `.env`, keys, dumps, and generated reports excluded
- ER diagram, relational schema, data dictionary, normalization proof, query catalogue, backup/restore proof, and attack-demo evidence included in the final report

---

## Documentation

| Document | Contents |
|---|---|
| [`PRD_Argus.md`](./PRD_Argus.md) | Full requirements, threat model, curriculum mapping, evaluation plan |
| [`Architecture.md`](./Architecture.md) | ER diagram, data flows, security architecture, key design decisions |
| [`Argus_Team_Development_Plan.md`](./Argus_Team_Development_Plan.md) | Task ownership, 11-week timeline, Gantt chart |

---

## Team

| Name | Track |
|---|---|
| Abhinav | Database Core, Security & Verification Engine |
| Nidhurshek | Application Layer, Dashboards & Integration |

---

*Academic project for BCSE302L Database Systems. Not intended for production use.*
