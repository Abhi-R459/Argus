# Production Operations Runbook

This repository now provides explicit deployment operations; it does not
provision a cloud environment or supply production credentials. Complete the
configuration checklist at the end before routing real users or storing real
employee data.

## Deployment order

1. Provision PostgreSQL 15 or newer with encrypted storage, automated point-in-
   time recovery if available, private networking, and an administrator
   credential stored outside the source tree. For Supabase Free, use the shared
   pooler session URL on port 5432 from IPv4-only environments. This application
   uses PostgreSQL's native protocol; it does not need Supabase Auth, the Data
   API, or a Supabase API key.
2. Configure the secrets and public-origin values listed below. Set
   `SIGNING_PRIVATE_KEY_FILE` to the mounted Ed25519 private key. Never commit
   `.env`, private keys, database dumps, or real personnel data.
3. For local Compose PostgreSQL only, start the database and wait for its
   healthy state. Hosted database deployments do not need the local `db`
   service:

   ```sh
   docker compose up -d db
   ```

4. Apply schema changes through the one-shot migration container. This job
   receives the database migration URL and cryptographic migration inputs;
   the API container does not receive `DATABASE_URL_MIGRATIONS`.

   For the Supabase Free project in this repository, set both
   `MIGRATIONS_DATABASE_URL` and `DATABASE_URL_MIGRATIONS` to the shared
   session-pooler URL using user `postgres.jdfakmmbydbnupndcytf`, database
   `postgres`, port `5432`, and `?sslmode=require`. Use the exact host copied
   from Supabase Connect and percent-encode the password. Never put this URL in
   the API's runtime URL variables.

   ```sh
   docker compose --profile ops run --rm migrate
   ```

5. Apply runtime role grants against the database named in the migration
   connection URL, then set separate random passwords for the HR and auditor
   database roles. `setup_roles.sql` grants `CONNECT` on the current database,
   so it works with local `argus` and hosted `postgres` database names.

   ```sh
   # Local Compose database
   docker compose exec -T db psql -U postgres -d argus < db/scripts/setup_roles.sql
   # Hosted or host-local database (uses DATABASE_URL_MIGRATIONS)
   python -m db.cli.setup_roles
   python -m db.cli.provision_roles
   ```
6. For local Compose, leave the runtime URLs unset so Compose uses the local
   defaults. For a hosted database, set `COMPOSE_DATABASE_URL_HR_ADMIN` and
   `COMPOSE_DATABASE_URL_COMPLIANCE_AUDITOR` to full
   `postgresql+asyncpg://` URLs using the respective least-privilege role,
   shared pooler host/port 5432, URL-encoded passwords, and `?sslmode=require`.
   Shared pooler usernames append the project ref, for example
   `hr_admin.jdfakmmbydbnupndcytf` and
   `compliance_auditor.jdfakmmbydbnupndcytf`.
   Keep the migration/administration URL separate from both runtime URLs.
   Build and start the API and frontend, then confirm the API health endpoint
   and frontend health check before enabling ingress traffic:

   ```sh
   docker compose up --build -d api frontend
   docker compose ps
   ```

7. Verify external checkpoint signatures/anchors and key custody independently.
   Compose's API readiness probe verifies both runtime database-role connections.
   `/api/health` is only process liveness and `/api/health/ready` is service
   readiness; neither endpoint verifies audit-chain integrity or external proof.
   The HR on-demand checkpoint endpoint (`POST /api/checkpoints/create`) is
   available only in development/demo while it uses the local file signer. The
   production API deliberately returns `503` until a managed signer is
   integrated. Migration `023_hr_checkpoint_creation` grants the HR role only
   the append-only database access needed by that route; applying the migration
   does not enable signing in production or create an external anchor.

## Backups

The manual backup job uses PostgreSQL custom format, writes into a temporary
directory with restrictive permissions, computes a SHA-256 sidecar, writes a
manifest, then atomically publishes the completed backup directory. A failed
dump is removed and does not appear as a completed backup.

```sh
docker compose --profile ops run --rm backup
```

The output is stored under `ARGUS_BACKUP_DIR` in a timestamped
`argus-<UTC timestamp>` directory. The default is `./backups` for local use.
This host directory is not off-site and is not durable production backup
storage by itself. Copy completed directories to independent, encrypted,
access-controlled storage and retain them according to your recovery-point and
retention requirements. Keep encryption and audit keys backed up separately
under a tested key-custody process; a database backup without the PII key does
not restore readable encrypted fields.

## Restore rehearsal

The included restore helper is deliberately restricted to an empty database
whose name starts with `argus_restore_`. It verifies the SHA-256 file and
PostgreSQL archive before restoring, refuses populated targets, and never drops
or cleans existing objects. It is a staging restore rehearsal, not an automated
production cutover procedure.

Create a fresh target database in the local Compose PostgreSQL instance, then
set `RESTORE_BACKUP_DIR`, `RESTORE_TARGET_DATABASE`, and
`ARGUS_RESTORE_CONFIRM=RESTORE:<exact target database name>` for that invocation:

```sh
docker compose exec db createdb -U postgres argus_restore_rehearsal
docker compose --profile ops run --rm restore
```

Afterward, validate the restored schema/data, apply the expected role grants,
run chain/checkpoint verification, and record the result of the rehearsal.
Repeat this procedure on a schedule using a disposable staging database. A
production outage recovery must follow the database provider's documented
restore/PITR procedure and be approved by the responsible operator.

## Configuration to supply before real deployment

| Configuration | Required action |
|---|---|
| Application environment | Set `APP_ENV=production`. Startup then fails closed unless Clerk issuer/authorized parties, HTTPS origins, TLS database URLs, cryptographic keys, role allowlists, and the mounted signing key are valid. Keep `APP_ENV=development` only for local work. |
| PostgreSQL | Select a managed or self-hosted service; configure TLS, private networking, encryption, automated snapshots/PITR where available, and a dedicated migration principal with only required privileges. On Supabase Free, the provided session pooler is IPv4-accessible; use port 5432 for this persistent API and encode special password characters in each URL. Provider-level recovery/backup features depend on the selected plan. |
| Runtime DB roles | Set unique high-entropy passwords for `hr_admin` and `compliance_auditor`; restrict network access and permissions to the Argus database. For Compose-hosted APIs, supply their full URLs through `COMPOSE_DATABASE_URL_HR_ADMIN` and `COMPOSE_DATABASE_URL_COMPLIANCE_AUDITOR`; leave them blank for local Compose PostgreSQL. |
| Migration/CLI connection | Configure `MIGRATIONS_DATABASE_URL` for the Compose migration job and `DATABASE_URL_MIGRATIONS` for local provisioning/administrative CLI tools. Administrative CLIs do not fall back to generic `DATABASE_URL`; they fail clearly when no dedicated URL or explicit `--db-url` is supplied. |
| Backup/restore credentials | Set the backup host, port, database, user, password, and SSL mode (`BACKUP_DATABASE_*`) for the actual database; the backup container uses PostgreSQL 17 client tools for the hosted PostgreSQL 17 project. Set separate `RESTORE_DATABASE_*` credentials and target a staging database. Ensure the backup identity can read all required objects. |
| Clerk | Create and verify the Production instance for the public application domain. Set its PEM public key in `CLERK_JWT_KEY`, its Frontend API URL as `CLERK_ISSUER`, and comma-separated exact HTTPS frontend origins in `CLERK_AUTHORIZED_PARTIES` and `CORS_ORIGINS`. The API verifies signature, issuer, expiry, subject, and `azp`; configure Clerk session claims to include the verified email fields used by first-time provisioning. Keep the two server-side role allowlists current. The browser only needs `VITE_CLERK_PUBLISHABLE_KEY`; never put Clerk's secret key in frontend build variables. |
| Cryptographic secrets | Generate and separately store `PII_ENCRYPTION_KEY`, `AUDIT_SALT`, `AUDIT_CONTEXT_SECRET`, and the Ed25519 signing key. Document ownership, access, backup, and rotation. Never reuse a key for another purpose. |
| Web origin and TLS | Set `CORS_ORIGINS` to the exact HTTPS origin(s), configure DNS and a TLS-terminating ingress, enforce HTTPS, and expose only ingress ports publicly. |
| Evidence anchoring | Choose and configure independently administered external anchor/witness providers, credentials, quorum policy, and retention. Verify checkpoints against a separately trusted public key. |
| Backup destination | Set `ARGUS_BACKUP_DIR` to a protected mount for local staging, then configure a separate scheduled copy to encrypted off-site/WORM storage, retention/lifecycle, access review, and alerting on missed runs. |
| Monitoring | Integrate container/database logs, metrics, uptime checks, disk/connection monitoring, security alerts, and an on-call escalation path. `/api/health` is process liveness; `/api/health/ready` checks both runtime DB roles. |
| Recovery | Define RPO/RTO, enable provider PITR/snapshots, rehearse restore and key recovery, validate audit-chain continuity after restoration, and document the cutover/rollback owner. |
| Deployment | Pin reviewed image versions/digests, configure CI secrets/protection, stage migrations with backup and rollback review, and deploy through a restricted operator workflow. |

Until these values and operational controls are supplied and tested, treat the
repository as a hardened deployment candidate rather than a fully production-
operated service.

### Clerk instance setup

The project must keep its Clerk Development and Production instances separate.
The current local `.env` is for Development. After the production hostname is
chosen and its DNS is available, authenticate and link the Clerk CLI, then run
`clerk deploy` in an interactive human terminal to create/configure the
Production instance and show the required DNS records. Verify progress with
`clerk deploy status`. Do not change `APP_ENV` to `production` or deploy the
Development publishable key/JWT public key as production credentials. Copy the
Production instance's public publishable key, exact Frontend API issuer, and
JWT PEM public key into the deployment secret/configuration store; the API does
not need Clerk's secret key to verify signed session tokens.

The database administrator/migration credential remains inside the trusted
operator boundary. Anyone with that credential can alter database objects and
bypass application audit controls; do not describe the system as resistant to
database-owner compromise. Use a separately controlled signing key and
independent external anchor/witnesses to make subsequent changes detectable.
