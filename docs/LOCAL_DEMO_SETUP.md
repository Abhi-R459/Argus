# Local Professor Demo Setup

This setup runs Argus on one laptop. It uses a dedicated local PostgreSQL
container and separate demo secrets; it does not connect the demo API, seed
job, or migrations to Supabase. Clerk Development remains an internet service,
so sign-in requires internet access. Use synthetic employee data only.

## Prepare the isolated demo configuration

From PowerShell at the repository root, create the demo-only configuration:

```powershell
python scripts/prepare_local_demo.py
```

The script reads only the Clerk Development publishable key, issuer, public
JWT-verification key, and the two role allowlists from `.env`. It generates
fresh local database passwords, PII/audit secrets, and a separate Ed25519 demo
signing key. It refuses to overwrite an existing `.env.demo` or signing key.
Both files are ignored by Git. Do not copy production credentials into these
files.

## Start the local stack

The separate Compose project name and volumes keep this demo database apart
from any existing Argus Compose database. Its ports are loopback-only:

```powershell
$compose = @('--project-name', 'argus-demo', '--env-file', '.env.demo', '-f', 'docker-compose.yml', '-f', 'docker-compose.local-demo.yml')
docker compose @compose up --build -d db
docker compose @compose --profile ops run --rm migrate
Get-Content db/scripts/setup_roles.sql | docker compose @compose exec -T db psql -U postgres -d argus
docker compose @compose --profile demo run --rm demo-provision
docker compose @compose up --build -d api frontend
```

Open `http://localhost:8088`. Confirm API readiness at
`http://localhost:8088/api/health/ready`. Sign in with the Clerk Development
HR and auditor accounts whose emails are in the two `.env` allowlists. Use
separate sessions for each role.

## Seed the walkthrough data

Only run these commands against the isolated `argus-demo` Compose project.
The default seeder resets demo employee, salary-history, audit, checkpoint,
and suspicious-flag rows in that local database:

```powershell
docker compose @compose --profile demo run --rm demo-seed
```

To append 40 additional synthetic employees while preserving the curated
walkthrough records, run this once:

```powershell
docker compose @compose --profile demo run --rm demo-seed python -m db.seed_demo --skip-purge --scale 40
```

`--skip-purge` is additive: every repeat adds another 40 employees and new
audit events. Do not run the seeder against Supabase or another shared
database.

### Verified local demo snapshot

After the append run on 2026-10-07, the local database contained 100
employees, 104 salary-history rows, 206 audit events, and 8 signed checkpoints.
The latest checkpoint covered sequence 200 while the audit tail was sequence
206. The Auditor Overview verified the hash chain, local anchor record, and
checkpoint signatures through sequence 206 (3/3 checks, zero anomalies).
This is a dated snapshot; later demo actions change these counts.

The local anchor is a file in the laptop's Docker volume, not an independent
trust domain. The current local demo has no persisted witness note, so Witness
Quorum is correctly reported as **Unverified**. Do not present it as an active
external 2-of-3 witness deployment.

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

To remove the isolated containers **and permanently delete this local demo
database and its anchor volume**, run:

```powershell
docker compose @compose down --volumes
```

## What to say during the presentation

Say that the walkthrough is running locally, with Clerk Development used for
sign-in. The local hash-chain verifier and signed evidence can be demonstrated;
the local anchor is not an independently operated external witness. Do not
describe this laptop setup as a hosted deployment or production service. Avoid
real personnel data.
