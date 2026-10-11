# Local Professor Demo Setup

The local walkthrough uses the regular `argus` Compose project for PostgreSQL,
the same host-run Uvicorn API and Vite frontend used in normal development, and
the standard Argus migrations, role provisioning, signing, anchoring, and
seeding tools. The API uses the local Docker database; it does not connect to
Supabase. Clerk Development remains an internet service, so sign-in requires
internet access. Use synthetic employee data only.

## Prepare the local settings

From PowerShell at the repository root:

```powershell
python scripts/prepare_local_demo.py
```

The script reads the Clerk Development publishable key, issuer, JWT public key,
and role allowlists from `.env`. It creates ignored `.env.local` settings with
fresh local database passwords, PII/audit secrets, and a separate Ed25519
signing key. It refuses to overwrite existing local settings or signing keys.
Do not copy production credentials into these files.

## First-time database setup

The Compose project is named `argus`. PostgreSQL listens on loopback port
5433. Host-run Uvicorn and the demo seed job share anchor files under the
ignored `anchor/local_demo` folder. The API and frontend run in your usual
terminals, outside Docker.

```powershell
$compose = @('--project-name', 'argus', '--env-file', '.env.local', '-f', 'docker-compose.yml')
docker compose @compose up -d db
docker compose @compose --profile ops run --rm migrate
Get-Content db/scripts/setup_roles.sql | docker compose @compose exec -T db psql -U postgres -d argus
docker compose @compose --profile demo run --rm demo-provision
docker compose @compose --profile demo run --rm demo-seed
```

The default seed resets demo employees, salary history, audit events,
checkpoints, and suspicious-flag rows. Run it only against this local database.
Do not point this seeder at Supabase or another shared database.

## Start the application the usual way

After the database is ready, start the API from the repository root:

```powershell
uvicorn api.main:app --host 127.0.0.1 --port 8000 --reload
```

Then in another terminal:

```powershell
cd frontend
npm run dev
```

Open `http://localhost:5173`. Vite proxies API requests to Uvicorn on port
8000. `.env.local` overrides the API's root `.env` settings so Uvicorn uses
the local Docker database and trusts the `localhost:5173` Clerk session.
Check database readiness at `http://localhost:8000/api/health/ready`.

To start the database again later, use:

```powershell
$compose = @('--project-name', 'argus', '--env-file', '.env.local', '-f', 'docker-compose.yml')
docker compose @compose up -d db
```

Do not rerun `demo-seed` on every startup; it resets walkthrough data.

## Add synthetic walkthrough data

To append 40 additional employees while preserving the curated walkthrough
records, define the Compose arguments in the repository root and run this once:

```powershell
$compose = @('--project-name', 'argus', '--env-file', '.env.local', '-f', 'docker-compose.yml')
docker compose @compose --profile demo run --rm demo-seed python -m db.seed_demo --skip-purge --scale 40
```

`--skip-purge` is additive: every repeat adds another 40 employees and new
audit events.

### Verified local demo snapshot

After the append run on 2026-10-07, the local database contained 100
employees, 104 salary-history rows, 206 audit events, and 8 signed checkpoints.
The latest checkpoint covered sequence 200 while the audit tail was sequence
206. The Auditor Overview verified the hash chain, local anchor record, and
checkpoint signatures through sequence 206 (3/3 checks, zero anomalies).
This is a dated snapshot; later demo actions change these counts.

The local anchor and witness files are stored under the ignored
`anchor/local_demo` directory, not in an independent trust domain. The current
local demo has no configured external witness quorum, so Witness Quorum is
correctly reported as **Unverified**. Do not present it as an active external
2-of-3 witness deployment.

### On-demand HR checkpoint

On `/hr/settings`, an authorized HR admin can create a signed checkpoint for
all events since the prior checkpoint. This requires migration
`023_hr_checkpoint_creation` and the local demo signing key. The action does
not create an external anchor; signing and anchoring are separate. After a new
checkpoint is created, use the configured verifier/anchor workflow before
claiming that the anchor comparison is verified. The production API currently
fails closed for this action until a managed signer is configured.

To stop the demo while preserving its local database and anchor volume:

```powershell
docker compose @compose down
```

To permanently delete the local Argus database and its anchor volume, run:

```powershell
docker compose @compose down --volumes
```

## What to say during the presentation

Say that the walkthrough is running locally, with Clerk Development used for
sign-in. The local hash-chain verifier and signed evidence can be demonstrated;
the local anchor is not an independently operated external witness. Do not
describe this laptop setup as a hosted deployment or production service. Avoid
real personnel data.
