# Clerk production release and rollback

Updated 21 October 2026. This is the release procedure for `arguss.in`. A
completed code build is not evidence that the public site is live. Record the
actual Render deployment IDs and verify the live site before changing status.

## Scope and access

- Clerk is the only sign-in provider. The existing Supabase project remains a
  PostgreSQL data store, with no Supabase Auth calls in the application.
- Every signed-in account may choose HR or Auditor in the UI and switch later.
  HR permits personnel and salary access. The API verifies the Clerk JWT,
  active Clerk session, verified primary email, and selected request role.
- Role choice is kept in browser session storage and sent to the API. The API
  applies the matching database login. Nobody needs to open Supabase or edit a
  table to choose a role.
- Clerk production instance: `ins_3L085Q4SCjxzCGXdSRQbbBdvqtr`, application
  `app_3J3THkzVki7iM1E0ivEdtIVVMmf`, domain `arguss.in`.
- Render frontend: `srv-db5qfenavr4c739nd0o0`; backend:
  `srv-db5qfenavr4c739nd0q0`. Keep the existing backend URL until a separate
  custom backend domain is planned.

## Release order

1. The registrar hold has been lifted and GoDaddy DNS editing is available.
   Keep GoDaddy nameservers and preserve the existing registrar records.
2. Add `arguss.in` to the Render static service (Hobby includes two custom
   domains). In GoDaddy DNS, replace the parked apex A record with the exact A
   target shown by Render, and point `www` at the Render static hostname.
   Preserve unrelated email and registrar records.
3. Add Clerk's DNS CNAME records shown on its production Domains page:

   | Host | Target |
   |---|---|
   | `clerk` | `frontend-api.clerk.services` |
   | `accounts` | `accounts.clerk.services` |
   | `clkmail` | `mail.lp7psncjpcqz.clerk.services` |
   | `clk._domainkey` | `dkim1.lp7psncjpcqz.clerk.services` |
   | `clk2._domainkey` | `dkim2.lp7psncjpcqz.clerk.services` |

   Verify records in Clerk and wait for its SSL certificates. DNS propagation
   may take up to 48 hours. Do not use development keys on the public site.
4. Create a Clerk production secret key in the Clerk dashboard. The account
   owner enters it directly into the Render backend environment as
   `CLERK_SECRET_KEY`. Configure `CLERK_JWT_KEY` with Clerk's production PEM
   public key and `CLERK_ISSUER` with its production JWT issuer. Set frontend
   `VITE_CLERK_PUBLISHABLE_KEY` to the production `pk_live_` key. Set
   `CLERK_AUTHORIZED_PARTIES` and `CORS_ORIGINS` to `https://arguss.in`.
   Preserve existing PII, audit context, signing, and database secrets.
5. Add the existing migration-administrator connection string as the
   `DATABASE_URL_MIGRATIONS` secret in the GitHub `production` environment.
   It must include the Supabase TLS options and CA path used by the deployment.
   Run **Argus production migrations** from `main`; the workflow accepts only
   revisions 033–035, applies additive migrations 034 and 035, then confirms
   revision 035. The credential is used only by this one-off job and is absent
   from the API runtime. No Supabase dashboard or table editing is needed.
   Deploy the API only after this workflow succeeds.
6. Set both Render services to the tested `main` branch and keep automatic
   deployment off. Deploy the backend first after migration and readiness pass;
   deploy the frontend only after the backend is healthy.
7. Verify HTTPS on `arguss.in`, Clerk sign-in, both role selections, role
   switching, HR undo for a newly created synthetic test record, auditor
   read-only views, and signed audit verification. Do not exercise a rollback
   on real employee records just to test it. Record exact deployment IDs and
   the read-only check result.

## Rollback

### Application release

Save both previous live Render deployment IDs and environment settings before
cutover. Render's Deploys page offers Rollback on earlier successful deploys.
Rollback the frontend and backend as a pair. Restore the previous authentication
environment settings and origin allowlist appropriate to that pair; a code
rollback alone cannot make a Clerk frontend talk to a Supabase Auth backend.
The additive migrations deliberately retain existing users and audit history.
Do not downgrade migrations on production unless separately reviewed and
backed up; old code ignores the new tables. Confirm readiness and sign-in after
the paired rollback.

### HR business action

HR's **Undo HR changes** page lists recent employee creations, profile edits,
and deactivations made after this release. Undo is a compensating action:
employee creation becomes inactive; a profile edit or deactivation restores
the encrypted prior state. The audit trail retains the original event and adds
the correction. An undo is refused if the employee changed afterward or the
receipt was already used. Salary history, departments, job roles, and changes
made before this release require an ordinary reviewed corrective action; the
page does not promise to reverse them. Never delete audit rows to undo work.

## Current status

- Code and automated tests are local; production deployment is not yet
  verified.
- Clerk production instance exists. Domain DNS and production secret setup
  remain pending.
- The registrar hold is lifted and DNS editing works. The live apex still
  resolves to GoDaddy parking IPs, `www` points to the apex, and all five
  Clerk CNAMEs are absent; Clerk reports the custom domain as unverified.
