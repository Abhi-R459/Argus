# Argus

Tamper-evident, self-verifying audit trails for PostgreSQL, demonstrated through a small Employee Records application. This is the BCSE302L Database Systems course project by Abhinav and Nidhurshek.

## Technology Stack

- React + Vite + Tailwind, Clerk React, React Hook Form, Zod, TanStack Query
- FastAPI, SQLAlchemy 2, Alembic, Pydantic
- PostgreSQL 15+ with `pgcrypto`, JSONB, triggers, views, functions/procedures, and row locking
- Clerk Hobby for authentication; local PostgreSQL `users.role` for authorization
- Docker Compose locally; Neon Free PostgreSQL, Render Free FastAPI, and a free static frontend host for deployment

## Installation and Execution

### Using Docker Compose (Recommended)

1. Copy `.env.example` to `.env` in the root and configure secrets (Clerk tokens, DB password).
2. Run `docker-compose up --build` from the root directory.
3. Access the frontend at `http://localhost:80` and the API at `http://localhost:8000`.

### Local Development

1. **Database:** Run `docker-compose up db -d` to start the PostgreSQL instance.
2. **Backend:**
   ```bash
   cd api
   pip install -r requirements.txt
   uvicorn main:app --reload --port 8000
   ```
3. **Frontend:**
   ```bash
   cd frontend
   npm install
   npm run dev
   ```

### Testing

**Backend (Pytest):**
```bash
cd api
pytest
```

**Frontend (Playwright):**
```bash
cd frontend
npx playwright test
```

**Load Testing (k6):**
```bash
k6 run benchmarks/load_test.js
```

The full setup, verifier, benchmark, native `pg_dump`/`pg_restore` recovery demonstration, Docker Hub, and submission-evidence instructions are in [Argus docs/README.md](<Argus docs/README.md>).

## Documentation

- [Product requirements](<Argus docs/PRD_Argus.md>)
- [Architecture, ER diagram, relational schema, and data dictionary](<Argus docs/Architecture.md>)
- [Team development plan and Gantt chart](<Argus docs/Argus_Team_Development_Plan.md>)

## Repository Hygiene

The repository is private, contains `main` and `dev` branches, uses pull requests, and excludes `.env`, private keys, anchors, and database dumps through `.gitignore`.
