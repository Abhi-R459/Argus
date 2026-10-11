# Argus launch handoff

Updated 11 October 2026. The application has been hardened and the existing Supabase Argus project has been upgraded to `026_checkpoint_boundary_lock`. The user requires zero paid services or expiring trials. Supabase's connected organization is confirmed on the Free plan. A public website has not been deployed. Vercel account access works and no Argus project is present. Render dashboard access now works: the workspace is on Hobby, has no card on file, no pending charges, and a monthly build-pipeline spending limit of **$0**. No hosting services have been created. The Render plugin is not exposed to this session. Clerk's dashboard is accessible, while its connector authentication remains unavailable.

## Recommended deployment

The free deployment template uses a **Render static site**, one **Render Free web service** for the Dockerized FastAPI API, and the existing **Supabase Free PostgreSQL** project. No paid disk, worker, cron service, new database, custom-domain purchase, trial or paid add-on is selected. The static site receives a provider address, such as `argus-frontend.onrender.com`; the actual available hostname must be read from Render after service creation. Signed checkpoints, business data and request budgets persist in PostgreSQL. Signing keys must be provisioned as provider secret files, never written dynamically to an ephemeral disk.

Render Free sleeps after 15 minutes without inbound traffic and can take about a minute to wake. It cannot attach a persistent disk, and background work stops while it sleeps. The frontend template uses a bounded 90-second request timeout; it does not automatically repeat a business write after an ambiguous network failure. Nonce cleanup and risk refresh run on API startup, and scheduled maintenance continues while the API is awake. Risk refresh is configured every five minutes. No artificial traffic or paid worker is configured to prevent sleeping.

This is a hardened deployment for small usage within free quotas, not continuous or guaranteed service. Render explicitly advises against its Free instances for production applications. Supabase Free can pause inactive projects, limits database size to 500 MB, and does not include downloadable managed daily backups. Keep independent database and key backups. Free plan availability and future pricing are controlled by the providers; no perpetual uptime or price guarantee can be made.

Vercel remains an optional frontend host only for a personal, non-commercial project: its Hobby terms restrict commercial use. Render static hosting is the default here so the deployment does not silently require Vercel Pro for a business application. Do not activate trials, add billing or upgrade plans. Before provisioning, verify the Render workspace's payment-method and overage settings; selecting Free compute alone does not prevent metered bandwidth/build charges on an account with billing enabled. With no payment method, Render suspends services/builds when the included quotas run out instead of charging.

Official references: [Render Free limits](https://render.com/docs/free), [Render Blueprints](https://render.com/docs/blueprint-spec), [Render secret files](https://render.com/docs/configure-environment-variables), [Supabase pricing](https://supabase.com/pricing), [Supabase backups](https://supabase.com/docs/guides/platform/backups), and [Vercel Hobby restrictions](https://vercel.com/docs/plans/hobby).

Render's dashboard currently includes 750 Free instance hours, 5 GB of bandwidth, 500 Starter build minutes, two custom domains and 25 services per month. Keep the existing $0 build spending limit and do not add a payment method. These are shared workspace quotas, not an allowance for every individual service. Use the API's provider hostname; do not add unnecessary custom domains beyond the included allowance. The original repository's Blueprint selected paid Starter compute and a disk: deploy only the updated free template from the reviewed release branch.

The GitHub repository is confirmed **public**. Its CI uses standard `ubuntu-latest` runners, which [GitHub provides free for public repositories](https://docs.github.com/en/billing/concepts/product-billing/github-actions). No larger runner or paid CI feature is configured. Render's public-repository source flow avoids granting a Git provider access to the account, but does not support automatic deploys or PR previews. Select the reviewed release branch explicitly rather than the repository's default `dev` branch, and manually deploy only after that commit's CI has passed and the production credentials are complete.

## Clerk and the pending free domain

The current implementation uses Clerk. [Clerk production deployment](https://clerk.com/docs/guides/development/deployment/production) requires a domain you control and access to its DNS records. A hosting provider's assigned address does not give you control over that provider's DNS. The current development issuer and `pk_test_` key remain rejected by production configuration. No domain purchase or production instance for an unowned hostname has been attempted.

The current path retains Clerk while seeking a suitable free domain. No Supabase Auth migration has been implemented. EU.org has a pending request for `argus-ledger.eu.org`, reference `20261011080447-arf-415`. Its nameserver, SOA and NS checks passed against `ns1.desec.io` and `ns2.desec.org`. The corresponding deSEC zone is active. A subsequent duplicate submission was ignored because this request already exists. EU.org must manually approve the request; the domain is not yet delegated or verified by Clerk. Do not resubmit or claim it is already approved. No card, payment or paid domain subscription was added. These providers offer free service today, without a guaranteed lifetime registration or availability promise.

After approval, configure DNSSEC by obtaining the zone's current DS records from deSEC and publishing them in EU.org's domain settings. Verify both delegation and the DNSSEC chain of trust. deSEC's [terms](https://desec.io/terms/) require secure delegation and permit deletion four weeks after a warning if delegation or DNSSEC remains missing. Keep control of the account email and respond to service notices. Record the actual hosting and Clerk DNS values after provisioning; do not invent target hostnames or add placeholder records. Clerk acceptance and certificate issuance for this delegated domain remain to be verified.

deSEC's setup dialog currently shows this **public** DS record, captured 11 October 2026. Recheck it in deSEC immediately before publishing because DNSSEC keys can change. It has not yet been submitted to EU.org:

```text
30133 13 2 f42d3a1b61119bf5ad5baf7a01517796f2a8b0da36f6b66fc9810e246ae9c9f7
```

Clerk Hobby is free within its quota. The development instance currently has **SMS code MFA**, a feature marked as requiring Pro in production; development instances can try paid features for free. Do not copy or enable that paid feature in production, start a trial, or upgrade the account. If a change would weaken an existing authentication setting, obtain confirmation for that specific change. Keep production configuration within free authentication features. Supabase Auth remains a fallback only if the domain cannot be approved or accepted; changing providers also requires a proper production email or OAuth flow.

## What is already completed

- Supabase project `jdfakmmbydbnupndcytf` has all four launch migrations applied. All 13 public tables have RLS; anonymous and authenticated Data API roles have no application-table privileges. Runtime users have neither superuser nor RLS-bypass privileges. Auditor employee reads use a masked view.
- Both databases have no employees, salaries, departments, job roles, audit entries, checkpoints, review flags, or active application users. The disabled maintenance user, chain-state singleton, migration history, and cryptographic configuration remain.
- Local demo records and old local anchor files were backed up before cleanup. Recovery material is ignored by Git and excluded from deployment images; it is not active application data. Keep it restricted and delete according to your retention policy.
- Production configuration rejects development Clerk issuers, unsafe origins, generic database roles, demo switching, diagnostic workloads, and missing or mismatched signing keys. Launch frontend builds require a production Clerk key and HTTPS API URL.
- Request bodies, database queries, connection waits, and browser requests are bounded. Per-user request limits persist in PostgreSQL across workers and restarts. National ID searches use a JSON request body, and the API rejects the former URL query form. Request logs omit bodies and queries, and validation errors avoid echoing submitted PII. Account changes receive separate browser caches.
- HR can create departments and job roles in Settings before registering the first employee. Diagnostic concurrency tools remain available only in explicitly enabled local development.

## Configure authentication

1. After EU.org approves the domain and delegation/DNSSEC are verified, create the Argus production instance for the confirmed domain. Complete Clerk's DNS, TLS and email-domain checks. Configure allowed redirects/origins for the exact frontend URL.
2. Require verified email. Use separate HR and auditor accounts and free authentication features only. Do not enable paid MFA, paid allowlisting, enterprise SSO, SMS or billing add-ons. The API independently restricts role provisioning to its approved-email lists. Do not place roles in user-editable metadata.
3. Configure [Clerk session-token custom claims](https://clerk.com/docs/guides/sessions/customize-session-tokens) used by the API:

   ```json
   {
     "email": "{{user.primary_email_address}}",
     "email_verified": "{{user.email_verified}}",
     "name": "{{user.full_name}}"
   }
   ```

   Confirm on an actual production token that `email_verified` is a JSON boolean, with valid `iss`, `azp`, `exp`, `iat`, and `sub` claims. Token verification uses Clerk's RS256 public key. Store the production PEM public key in `CLERK_JWT_KEY` and the exact issuer in `CLERK_ISSUER`. Update that PEM when Clerk rotates signing keys; redeploy and verify login.
4. Put approved verified email addresses into the API's `HR_ADMIN_EMAILS` and `COMPLIANCE_AUDITOR_EMAILS`. The lists must not overlap. First sign-in provisions the approved role. Subsequent changes to these lists do not revoke or change existing database roles: an administrator must deactivate or update the application user explicitly. Keep production administration credentials outside the API.

## Configure the API

Use `render.yaml` and `.env.production.example` as templates. The API image defaults to production; local container checks explicitly select development. Add secrets in the provider dashboard; do not upload local `.env` files, demos, snapshots, backups, or migration administrator credentials.

- Use the database's dedicated `hr_admin` and `compliance_auditor` passwords. Separate strong passwords have now been installed and saved only in the ignored `.env.production`, with restricted Windows file access. The dashboard confirms the free session-pooler host `aws-0-ap-south-1.pooler.supabase.com`, port **5432**, database `postgres`, and usernames `hr_admin.<project-ref>` / `compliance_auditor.<project-ref>`. URL-encode passwords. Transaction pooling on port 6543 is not the configured deployment mode.
- Database TLS verifies the certificate and hostname. The Docker image includes Supabase's public CA at `/app/certificates/supabase-ca.crt`. Keep `sslmode=verify-full&sslrootcert=/app/certificates/supabase-ca.crt` in both production URLs. Both runtime roles have connected through the actual pooler with these checks enabled; the auditor still has no raw employee-table SELECT grant. The client no longer relies on an implicit per-machine PostgreSQL certificate file. See `certificates/README.md` for the trust root's source and fingerprint.
- Preserve the database's existing `AUDIT_CONTEXT_SECRET` and key ID; the database verifies signatures against its installed key. Replacing only the API value will break writes. Provision fresh PII encryption and audit-index secrets for a new database, or preserve existing values when there is encrypted/indexed history. Back up all keys independently of database backups.
- The empty hosted database now has a separate production actor key, `production-20261011`. A challenge-response check confirms that it matches the ignored production configuration; the former hosted `v1` key is disabled. Local demo configuration is unchanged. Fresh production encryption, audit-index and Ed25519 signing keys were created separately under restricted local storage. Mount `keys/production/verifier_private_key.pem` and `keys/production/public_key.pem` as the two Render secret files. Those private files are not part of Git or the image. Administrator access used for key installation was revoked before its transaction committed. Future rotations use the maintenance CLI, which restores temporary owner-role membership and refuses to disable the last enabled key.
- Add `verifier_private_key.pem` and its matching `public_key.pem` as **Render secret files**. They appear at `/etc/secrets`. Never generate a replacement signing key automatically during deployment. Retain trusted historical public keys if rotating keys later.
- Keep `ANCHOR_STORE=none` for the free deployment. Checkpoints are signed and stored in PostgreSQL; the API and UI report external anchoring as missing and independent witness verification as unknown. No local anchor file is treated as durable production evidence. Retain downloaded signed evidence separately if needed. The API's manual checkpoint operation does not publish an external anchor.
- Set `CORS_ORIGINS` and `CLERK_AUTHORIZED_PARTIES` to the exact production frontend origin. Do not enable wildcard or arbitrary preview-domain access. Keep demo switching and concurrency diagnostics disabled.
- Start with the configured small connection pools and one API instance. Apply future migrations with a separate administration process before deploying code that requires them; never have every API worker run migrations at startup.
- Run `python scripts/check_production.py` in the configured environment, then confirm `/api/health/ready` returns 200. This checks configuration and key pairing without changing records. Readiness checks both actual runtime roles and the request-budget function.

Local public keys and secret files are not committed. The production example contains placeholders deliberately; it cannot be deployed unchanged.

## Configure the frontend

The default `render.yaml` includes the free static site, Node **22**, SPA routing, cache/security headers and the strict `npm run build:production` command. Use only frontend variables:

```text
VITE_CLERK_PUBLISHABLE_KEY=pk_live_<production-publishable-key>
VITE_API_URL=https://api.<domain>/api
VITE_ENABLE_DIAGNOSTICS=false
VITE_API_TIMEOUT_MS=90000
```

Use the actual API provider hostname in `VITE_API_URL`. Set API CORS and authorized parties to the actual frontend HTTPS origin. Every `VITE_` value is public in the browser. Never put a Clerk secret key, database password, encryption key, actor secret, or signing key there. If using Vercel for a personal non-commercial deployment, use project root `frontend` and keep `vercel.json`; it enforces the same strict build. Verify HTTPS before testing authentication.

## Release verification

CI runs backend and database unit tests, browser tests, dependency audits, and fresh PostgreSQL migrations with explicit disposable-database isolation. Local fixtures in test source remain necessary; they are not seeded into production or included in the API image. Development browser role shortcuts are compiled out of production bundles.

Run the read-only public checks after deployment. Use actual provider origins, without `/api` in the API origin:

```text
python scripts/check_live_deployment.py --frontend-origin https://<frontend-host> --api-origin https://<api-host>
```

This requires valid HTTPS, database readiness, frontend routes and security headers, rejection of anonymous and invalid-token access, restricted CORS, and disabled API documentation. It makes no business writes, uses no real credentials, and reports no response bodies. It allows a free host time to wake and does not follow redirects or bypass certificate validation. Passing this check does not prove real authentication, role isolation or recovery.

Before announcing availability, complete the checks that depend on the live domain:

1. Verify sign-in, sign-out, expiry, refresh, deactivation, and wrong-role denial using real Clerk production accounts. Anonymous users must not see protected data.
2. With approved operational data, create the first department, role, employee, and salary. Confirm the audit trail, checkpoint signature, evidence download and auditor PII masking. Use a staging database for throwaway tests; preserve production audit history once real usage begins.
3. Test backup restoration into an isolated database and recovery of signing/encryption keys and separately retained evidence. Supabase Free has no downloadable managed daily backups; use the existing backup tooling with protected storage outside the database. Do not enable paid backups or PITR. Backup frequency and manual recovery determine the achievable data-loss and recovery windows.
4. Configure uptime alerts on API readiness, deployment failure alerts, and alerts for repeated background-job failures. Logs include request IDs and omit request queries and bodies. Review hosting-provider access-log handling before enabling sensitive national-ID searches.
5. Load-test realistic concurrent traffic and growing ledgers in staging. Whole-ledger verification still needs sizing at production scale. Interactive evidence exports are capped at 50,000 events; checkpoints seal batches of at most 10,000 events. Use offline tools for larger exports. Browser checks use mocked API responses; they do not replace real authentication or load testing.
6. Establish data retention, access review, incident response, and the required privacy notice for employee data before inviting users.

## Audit trust and deployment limits

The API is designed for **one organization**. Adding multiple customers requires organization IDs, tenant-scoped authorization, and tenant isolation across tables and views before shared hosting.

The signing key resides with the API in this initial deployment. A compromised API can use it. The free deployment has no independent external anchor or witness. It cannot claim protection against a complete rollback of the database and its checkpoints together. Independently retained signed evidence can help compare later state, but a complete independent publication design is not included. Do not describe the bundled in-process witness simulation as independent production witnesses.

Supabase's post-migration security advisor reports an informational notice for the private request-budget table having RLS without a policy. This is intentional: direct runtime and Data API table access is denied; only its restricted SECURITY DEFINER function and its non-login owner access it. Unused-index notices are expected on an empty database; retain indexes until actual traffic provides evidence for changes.

Domain approval and Clerk acceptance, working hosting connections, safe free-account billing settings, live-host checks, monitoring and recovery validation remain launch gates. The configuration retains Clerk while its free-domain request is pending. The four clearly labelled Clerk development test accounts were permanently removed after the user's specific approval; the five real accounts remain. Clerk's workspace is confirmed on Hobby. No claim of a completed public deployment or error-free production operation is made.

## Validation recorded for this handoff

- API: 151 tests passed, including private search access, URL rejection, redacted validation, durable rate limits, verified database TLS, and ten checks of the public deployment verifier. Database units: 216 passed; 42 opt-in or specialized checks are skipped in the ordinary unit run. Four explicitly isolated live PostgreSQL checks passed previously; the current CI also includes two PostgreSQL 17 key-rotation cases for restricted administrator membership and last-key protection.
- Browser: all 24 tests passed, including a check that national IDs never appear in request URLs, empty-organization setup, role protection, workflow refresh, counterfactual replay, and evidence downloads. These are mock-API browser checks; real Clerk production authentication remains pending.
- Frontend lint and compilation passed. The strict launch build deliberately rejected the current Clerk development key. Production frontend credentials have not been fabricated or deployed.
- Python and frontend dependency audits reported no known vulnerabilities in the checked lockfiles.
- Docker build passed; the non-root container started against the local runtime roles, passed readiness, returned privacy headers, and denied anonymous employee access. Secrets and demo seed data are excluded from its image.
- Cleanup backup restoration passed in an isolated temporary database: 101 employees, 209 audit events and 13 checkpoints restored. Temporary databases and active local anchor files were removed afterward. The recovery dump remains under `backups/pre-launch-cleanup-20261011T043421Z/`.
- Hosted and local databases are at `026_checkpoint_boundary_lock`, with zero active application users, employees, salaries, audit events, job roles and departments. Public hosting deployment, production recovery testing and load testing are pending. The reviewed release branch is `codex/production-launch`. The first release commit, `23feaac`, passed [both remote CI jobs](https://github.com/Abhi-R459/Argus/actions/runs/38128290944). Check the current branch's latest CI result before manually deploying; the subsequent privacy, certificate and key-maintenance updates require their own checks. Render has accepted this branch's Blueprint preview; its secret fields remain empty and no services have been deployed.
