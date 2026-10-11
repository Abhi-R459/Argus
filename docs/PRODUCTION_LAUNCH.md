# Argus launch handoff

Updated 11 October 2026. The user requires free services only, with no card,
paid upgrade, expiring trial or paid add-on. The application now uses Supabase
Auth with Google OAuth. The existing Supabase Free project is at migration
`027_supabase_sessions`. Google consent and its web client have been created;
Google login is enabled in Supabase, Email login is disabled, and both approved accounts are saved in Google’s restricted access list. Public hosting is still pending. No live app URL is
claimed in this handoff.

## Free deployment

Deploy the reviewed `codex/production-launch` branch using `render.yaml`: one
Render Free Docker API, one Render static site, and the existing Supabase Free
project. The repository's default `dev` branch must not be used: its old
Blueprint selected paid compute and a disk. Automatic deploys are disabled for
the public repository source; deploy only after the exact release commit's CI
passes. The public GitHub repository uses ordinary free Actions runners.

The Render workspace was verified on Hobby with no card or pending charges and
a **$0 build-pipeline spending limit**. Recheck before creating services. Do not
add billing, workers, cron services, disks, new databases, trials or paid custom
domains. The observed shared quotas were 750 Free instance hours, 5 GB bandwidth,
500 Starter build minutes, two custom domains and 25 services. With no payment
method, quota exhaustion stops service/builds rather than authorizing charges.
Provider terms and quotas can change; free forever and uninterrupted service
are not guaranteed.

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
Vercel Hobby restricts commercial use, so Render static hosting is the default.

## Authentication

Google OAuth uses Supabase's free project callback:
`https://jdfakmmbydbnupndcytf.supabase.co/auth/v1/callback`.
A purchased domain and custom Supabase Auth domain are unnecessary. Request only
openid, email and profile; no paid Google Cloud API is needed. Store the Google
client secret only in Supabase's Google provider settings. Keep nonce checks
and email confirmation enabled, anonymous login and manual linking disabled,
and disable unused Email login once Google is enabled. Use the actual frontend
HTTPS origin for the Auth Site URL and its exact `/auth/callback` address in the
redirect allowlist. Never use wildcard preview domains.

Approved identities:

| Role | Verified Google email |
|---|---|
| HR administrator | evillegend045@gmail.com |
| Compliance auditor | abhinavreddykarnati@gmail.com |

The API derives permissions from its separate server-side email lists. It
validates the access token with Supabase Auth, then checks current verified
Google identity, user ban/deletion state and the signed session ID against
`auth.sessions`. Logout revokes access immediately. Existing application
profiles are rechecked against the current email and role on every request;
removing an email from its list removes its access. `user_metadata` never grants
permissions. First approved sign-in provisions the application profile.

Migration 027 exposes only a private boolean session check to the HR database
pool. Its owner cannot log in and can read only session-status and user
ban/deletion columns. Neither runtime business role can read Auth passwords,
refresh tokens or credential tables. The legacy internal `clerk_user_id` column
is retained to preserve audit references and now stores `supabase:<uuid>`;
the API exposes it as `auth_user_id`. Clerk is unused by the deployed code.

A standalone PostgreSQL database has no Supabase Auth sessions and deliberately
fails real session checks closed. Real login requires connecting the API to the
same Supabase project as Auth. Unit/browser/isolated PostgreSQL tests mock
external identity rather than weakening the deployed checks.

## Data and database security

The hosted project is `jdfakmmbydbnupndcytf`, region ap-south-1, on Free. Its
business tables contain no employees, salary records, departments, roles,
audit entries, checkpoints or active application users. Auth currently has no
users. The disabled maintenance identity, chain singleton, migration history
and cryptographic configuration are intentional infrastructure.

Local demo data was also emptied after a backup. Its recovery dump under
`backups/pre-launch-cleanup-20261011T043421Z/` restored successfully into an
isolated database: 101 employees, 209 audit events and 13 checkpoints. Recovery
material is ignored by Git and excluded from deployment images. Local tests
remain in source but never seed production.

All 13 public tables have RLS. Supabase anonymous/authenticated Data API roles
have no application-table privileges; runtime roles are neither superusers nor
RLS-bypass roles. Auditor employee reads use a masked view. The security advisor
has one informational notice: the private request-budget table has no RLS
policy because direct access is intentionally denied; only its restricted
function can use it.

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
unchanged. Add the two runtime database URLs, PII key, audit salt and actor
assertion secret to Render's secret environment. Preserve the matching installed
actor key ID `production-20261011`; the old hosted v1 actor key is disabled.
Never replace only one side of an actor-key configuration. Back up encryption
and signing keys separately from the database.

Mount the restricted production `verifier_private_key.pem` and matching
`public_key.pem` as Render secret files at `/etc/secrets`. No private key is
in Git or the image. The API requires its expected public key to match and will
not silently generate a replacement key. Retain historical trusted public keys
when rotating. Set exact frontend HTTPS `CORS_ORIGINS`, keep demo switching and
concurrency diagnostics disabled, and use the configured small connection pools.
Apply migrations through a separate administrator before deploying code; workers
do not run migrations at startup.

`ANCHOR_STORE=none`: signed checkpoints persist in PostgreSQL. External anchoring
is missing and independent witness verification is unknown. The signing key
resides with the API; API compromise can use it. A complete rollback of both
business data and checkpoints requires independently retained evidence to
detect. No KMS, HSM or independent witness has been configured for this free
launch. The application supports one organization; shared multi-customer hosting
requires explicit tenant isolation first.

## Frontend configuration

Set only public values on the static site, using Node 22 and
`npm run build:production`:

```text
VITE_SUPABASE_URL=https://jdfakmmbydbnupndcytf.supabase.co
VITE_SUPABASE_PUBLISHABLE_KEY=sb_publishable_<public-key>
VITE_API_URL=https://<actual-api-host>/api
VITE_ENABLE_DIAGNOSTICS=false
VITE_API_TIMEOUT_MS=90000
```

Read the actual API/frontend hostnames from Render after provisioning rather
than inventing them. Every `VITE_` value is publicly visible. Never add Google
client secrets, Supabase secret/service-role keys, database passwords, encryption
keys or signing keys. The client uses PKCE and a single shared token refresh;
account changes get separate workspace caches. Failed sign-out asks for retry
rather than pretending the server session was revoked.

## Release checks and remaining work

Local validation passed: **178 API tests**, **216 database unit tests** with
44 opt-in/specialized skips, **27 browser tests**, and **eight isolated PostgreSQL
17 checks**. The fresh-database checks include session expiry/logout/ban/deletion,
minimum Auth column grants, restricted migration-administrator permission
restoration, signed writes and checkpoint verification. Frontend lint and the
strict launch build passed using the public Supabase configuration. Browser
tests use mocked APIs and do not establish real Google login. The API image
build and packaging checks passed; production keys/configuration and hosted database readiness also passed with a temporary test origin. Remote CI and live startup must use this updated release and the actual hosting origin.

Before announcing availability, provision the free Render services and
secret files, and set exact Auth redirects/CORS. Verify the exact commit's CI.
Then run the read-only deployment check:

```text
python scripts/check_live_deployment.py --frontend-origin https://<frontend-host> --api-origin https://<api-host>
```

It checks HTTPS, readiness, frontend routes/security headers, anonymous and
invalid-token rejection, CORS and disabled API documentation without business
writes. Separately verify both approved real Google accounts, wrong-role denial,
sign-out, session refresh and deactivation. Synthetic workflow/load tests belong
in an isolated staging database; production audit history must be preserved once
real usage begins. HR Settings can create the initial department and job role
without demo data.

Establish independent backups and a restore/key-recovery rehearsal, readiness
and deployment-failure alerts, access reviews, retention and an employee privacy
notice. There is no paid backup/PITR or automatic free-host uptime guarantee.
Evidence exports are capped at 50,000 events and checkpoints at 10,000 events;
size real workloads in staging before exceeding the free deployment's capacity.

## Pending optional domain

EU.org request `argus-ledger.eu.org`, reference `20261011080447-arf-415`, is still
pending manual approval; its deSEC zone and nameserver checks passed. The new
Supabase login path does not depend on it. Do not resubmit or claim approval.
If approved later, verify delegation and publish fresh deSEC DNSSEC DS records
before using it. EU.org/deSEC are free today, without a lifetime guarantee.
The four explicitly approved Clerk development test accounts were removed;
five real Clerk accounts were retained and are not used by this release.
