# Argus

Tamper-evident, self-verifying audit trails for PostgreSQL, demonstrated through a small Employee Records application. This is the BCSE302L Database Systems course project by Abhinav and Nidhurshek.

## Technology Stack

- React + Vite + Tailwind, Clerk React, React Hook Form, Zod, TanStack Query
- FastAPI, SQLAlchemy 2, Alembic, Pydantic
- PostgreSQL 15+ with `pgcrypto`, JSONB, triggers, views, functions/procedures, and row locking
- Clerk Hobby for authentication; local PostgreSQL `users.role` for authorization
- Docker Compose locally; Neon Free PostgreSQL, Render Free FastAPI, and a free static frontend host for deployment

## Installation and Execution

1. Copy `.env.example` to `api/.env` and supply local or deployment secrets.
2. Start PostgreSQL locally through Docker Compose, then run `db/setup_roles.sql` and `alembic upgrade head`.
3. Install backend dependencies from `api/requirements.txt` and frontend dependencies from `frontend/package.json`.
4. Run `uvicorn main:app --reload` in `api/` and `npm run dev` in `frontend/`, or use `docker compose up --build`.

The full setup, verifier, benchmark, native `pg_dump`/`pg_restore` recovery demonstration, Docker Hub, and submission-evidence instructions are in [Argus docs/README.md](<Argus docs/README.md>).

## Documentation

- [Product requirements](<Argus docs/PRD_Argus.md>)
- [Architecture, ER diagram, relational schema, and data dictionary](<Argus docs/Architecture.md>)
- [Team development plan and Gantt chart](<Argus docs/Argus_Team_Development_Plan.md>)

## Repository Hygiene

The repository is private, contains `main` and `dev` branches, uses pull requests, and excludes `.env`, private keys, anchors, and database dumps through `.gitignore`.
