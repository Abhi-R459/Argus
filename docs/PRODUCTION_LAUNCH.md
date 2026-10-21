# Argus launch handoff

> **Current release:** The Clerk and `arguss.in` migration is tracked in
> [Clerk production release and rollback](CLERK_PRODUCTION_RELEASE.md).
> This page records the earlier Supabase Auth launch and its dated observations.

Updated 21 October 2026. The user requires free services only, with no card,
paid upgrade, expiring trial or paid add-on. The application now uses Supabase
Auth with Google OAuth. Migration `031_checkpoint_schedule_settings` adds the
HR automatic checkpoint schedule; migrations 032-033 apply subsequent access
policy updates. Confirm the deployed database revision before claiming those
changes are live. Google login is enabled in Supabase, Email login is disabled,
and approved accounts are saved in Google's restricted access list. The
approved Render Free API and static site have been provisioned:

| Resource | Actual assigned address / ID |
|---|---|
| Application | https://argus-frontend-0i6n.onrender.com |
| API | https://argus-backend-u0i3.onrender.com |
| API service | `srv-db5qfenavr4c739nd0q0` |
| Static service | `srv-db5qfenavr4c739nd0o0` |
| Blueprint | `exs-db5lc92d0e5s73fsbkt0` |

The API stores its runtime secrets and two signing files only in its backend
configuration. The frontend has public Auth configuration and the API address.
Supabase Site URL and its one callback redirect match the actual frontend.
The 11 October release and deployment IDs below are historical. On 21 October,
the functional audit recorded the frontend deployed from `26dd494` and backend
from `a11d951`; the backend deployment included a production-discovered replay
fix. See the [production functional audit](PRODUCTION_FUNCTIONAL_AUDIT_2026-10-21.md)
for the tested workflows and exact limits. The live Render environment and
source revision should be rechecked after each later release.

**21 October audit update:** The release IDs and empty-data assumptions above are
the 11 October launch snapshot, not a current production attestation. A live
auditor session on 21 October showed 102 employee inserts, 106 salary-history
inserts, 212 audit entries, three checkpoints, and a private GitHub anchor with
two entries beyond it. The exact deployed source commit and effective Render
environment were not independently confirmed. Treat the existing synthetic
QA records as part of this instance's permanent audit history; do not remove
them directly from the ledger. See
[`PRODUCTION_FUNCTIONAL_AUDIT_2026-10-21.md`](PRODUCTION_FUNCTIONAL_AUDIT_2026-10-21.md)
for the observed feature matrix and limitations.

## Free deployment

Deploy both production Render services from `main` using `render.yaml`: one
Render Docker API, one Render static site, and the existing Supabase PostgreSQL
project. Do not use `dev` or preview branches for production. Automatic deploys
remain disabled; deploy only after CI passes for the exact `main` commit and the
controlled production migration workflow succeeds. Blueprint Auto Sync is set
to **No**, so future YAML changes require a deliberate manual sync. The public
GitHub repository uses ordinary free Actions runners.

The Render workspace was verified on Hobby with no card or pending charges and
a **$0 build-pipeline spending limit**. Recheck before changing services. Do not
add billing, workers, cron services, disks, new databases, trials or paid custom
domains. The observed shared quotas were 750 Free instance hours, 5 GB bandwidth,
500 Starter build minutes, two custom domains and 25 services. With no payment
method, quota exhaustion stops service/builds rather than authorizing charges.
Provider terms and quotas can change; free forever and uninterrupted service
are not guaranteed. The quoted plan and quota figures are dated observations,
not a current account or billing check.

Render Free sleeps after 15 minutes idle and may take about a minute to wake.
The frontend allows a bounded 90-second API request and never automatically
repeats a business write after an ambiguous failure. Background maintenance
runs on startup and while the API is awake; there is no artificial keepalive.
Supabase Free can pause inactive projects and has a 500 MB database limit.
It has no downloadable managed daily backups. Preserve independent backups.
This setup suits small usage within free limits; it has no uptime guarantee.

References: [Render Free](https://render.com/docs/free),
[Blueprint specification](https://render.com/docs/blueprint-spec),
[Render secret files](https://render.com/docs/configure-environment-variables),
[Supabase pricing](https://supabase.com/pricing), and
[Supabase backups](https://supabase.com/docs/guides/platform/backups).
Render static hosting is the production frontend.

## Authentication

Clerk is the only authentication provider. Each signed-in account with a
verified primary email may choose either the HR or Auditor workspace in the UI
and switch later. The selection is a browser-session preference, not a durable
privilege grant. The API validates the Clerk JWT, checks the current Clerk
session and account state, then routes each request through the matching
PostgreSQL login. HR access is intentionally available to any signed-in account
because that is the approved product policy; protect access to the app and its
production data accordingly.

The `users` table remains the application identity store. Migration 034 links a
Clerk subject to a stable existing Argus user by verified email, preserving user
IDs and audit references. New accounts are provisioned by the app at first
sign-in. No one needs to open Supabase or edit user records to select a role.
Migration 035 stores encrypted preimages for the supported HR undo actions.
Apply both through the controlled **Argus production migrations** GitHub
workflow; the migration administrator is a one-off credential and is not part
of the API runtime.

A standalone PostgreSQL database cannot verify live Clerk sessions; the API
fails closed if Clerk configuration or session verification is unavailable.
Unit, browser and isolated PostgreSQL tests mock external identity rather than
weakening production checks. The Supabase Data API is not used for sign-in or
business-table access.

## Data and database security

The hosted project is `jdfakmmbydbnupndcytf`, region ap-south-1, on Free. The
21 October production browser audit observed 102 synthetic QA employee inserts,
106 salary-history inserts, 212 audit entries, and three checkpoints. The
latest observed private GitHub anchor was two entries behind the ledger; the
independent witness quorum was unverified. These are dated observations, not
live counters. Treat the synthetic events as permanent audit history; do not
delete rows directly. The production functional audit records the time and
scope of the observation.

Local recovery data is stored outside Git and excluded from deployment images.
The local snapshot is for isolated demonstrations and is separate from the
hosted database. Never point local seed, attack, or destructive test commands at
the production project.

The local database was empty after the 11 October launch cleanup, then the
available isolated backup was restored for the 21 October demonstration setup.
That restored snapshot contains 101 employees, 209 audit events, and 13
checkpoints. It is separate from production and can change during local demos.
Recovery material is ignored by Git and excluded from deployment images. Local
tests and seed tools must never target production.

All 13 public tables have RLS. Supabase anonymous/authenticated Data API roles
have no application-table privileges; runtime roles are neither superusers nor
RLS-bypass roles. Auditor employee reads use a masked view. The security advisor
has one informational notice: the private request-budget table has no RLS
policy because direct access is intentionally denied; only its restricted
function can use it. The advisor also reports disabled leaked-password
protection; password authentication is disabled in Clerk and the application
requires a verified primary email. See the
[private-table notice](https://supabase.com/docs/guides/database/database-linter?lint=0008_rls_enabled_no_policy)
and [password-protection guidance](https://supabase.com/docs/guides/auth/password-security#password-strength-and-leaked-password-protection).

The actual free session pooler is `aws-0-ap-south-1.pooler.supabase.com:5432`,
database `postgres`. Runtime usernames are `hr_admin.<project-ref>` and
`compliance_auditor.<project-ref>`, with separate strong passwords stored in the
ignored, restricted `.env.production`. Require
`sslmode=verify-full&sslrootcert=/app/certificates/supabase-ca.crt`.
Both roles passed certificate/hostname-verified connections; plaintext was
rejected with Supabase SSL enforcement enabled. Do not use transaction port
6543 or migration credentials in the API runtime.

## API secrets and configuration

Use `.env.production.example` and `render.yaml`; templates cannot be deployed
unchanged. Keep the HR and Auditor PostgreSQL runtime URLs, PII key, audit salt,
actor assertion secret, and signing material in Render's restricted environment.
Preserve the matching installed actor key ID `production-20261011`; never
replace only one side of an actor-key configuration. Back up encryption and
signing keys separately from the database.

The API requires Clerk's production `CLERK_SECRET_KEY`, `CLERK_JWT_KEY` public
PEM, `CLERK_ISSUER`, and the exact `CLERK_AUTHORIZED_PARTIES` origin. The
account owner has entered the secret key directly in Render. Never copy any
secret into source control or chat. Keep the migration administrator in the
GitHub `production` environment as `DATABASE_URL_MIGRATIONS`, separate from
both API database URLs.

Mount the restricted production `verifier_private_key.pem` and matching
`public_key.pem` as Render secret files at `/etc/secrets`. No private key is in
Git or the image. The API requires its expected public key to match and will not
silently generate a replacement key. Retain historical trusted public keys
when rotating. Set exact frontend HTTPS `CORS_ORIGINS`, keep concurrency
diagnostics disabled, and use the configured small connection pools. The
controlled GitHub migration workflow applies additive schema changes before
API deployment; services do not run migrations at startup.

The checked-in Blueprint defaults to `ANCHOR_STORE=none`, while the 21 October
live auditor view reported a configured private GitHub anchor. Confirm the
effective Render value and anchor repository without copying credentials into
this document. Independent witness verification was not established by that
historical observation. The signing key resides with the API; API compromise
can use it. No KMS, HSM or independent witness has been configured for this
launch. The application supports one organization; shared multi-customer
hosting requires explicit tenant isolation first.

## Frontend configuration

Set only public values on the Render static site, using Node 22 and
`npm run build:production`:

```text
VITE_CLERK_PUBLISHABLE_KEY=pk_live_<production-publishable-key>
VITE_API_URL=https://argus-backend-u0i3.onrender.com/api
VITE_ENABLE_DIAGNOSTICS=false
VITE_API_TIMEOUT_MS=90000
```

Every `VITE_` value is public. Never add Clerk secret keys, database passwords,
encryption keys or signing keys to frontend configuration. Configure `arguss.in`
as the production app origin in Clerk, CORS, and authorized parties. Keep the
backend URL on its existing Render hostname.

## Release checks and remaining work

The older Google/Supabase launch and test counts above are historical evidence;
they do not verify this Clerk release. For the current release, run CI on the
exact `main` commit, run the **Argus production migrations** GitHub workflow,
then manually deploy the API and frontend Render services from `main`. Deploy
the API after migrations and readiness succeed, then deploy the frontend.
Follow [the Clerk production release and rollback runbook](CLERK_PRODUCTION_RELEASE.md)
for the ordered provider setup, checks and rollback procedure.

The read-only deployment check is:

```text
python scripts/check_live_deployment.py --frontend-origin https://arguss.in --api-origin https://argus-backend-u0i3.onrender.com
```

It checks HTTPS, readiness, frontend routes/security headers, anonymous and
invalid-token rejection, CORS and disabled API documentation without business
writes. Separately verify sign-in, first-time workspace selection, switching
between HR and Auditor, HR undo using a newly created synthetic record, auditor
read-only views and signed audit verification. Do not exercise a data rollback
on real personnel records. Do not report a successful launch until these live
checks pass.

Continue to establish independent backups and a restore/key-recovery rehearsal,
readiness and deployment-failure alerts, access reviews, retention and an
employee privacy notice. There is no paid backup/PITR or automatic free-host
uptime guarantee. Evidence exports are capped at 50,000 events and checkpoints
at 10,000 events; size real workloads in staging before exceeding the free
deployment's capacity.

## Pending optional domain

EU.org request `argus-ledger.eu.org`, reference `20261011080447-arf-415`, is still
pending manual approval; its deSEC zone and nameserver checks passed. The new
Supabase login path does not depend on it. Do not resubmit or claim approval.
If approved later, verify delegation and publish fresh deSEC DNSSEC DS records
before using it. EU.org/deSEC are free today, without a lifetime guarantee.
The old Clerk references describe historical schema/account migration details;
deployed authentication uses Supabase Auth with Google OAuth.
