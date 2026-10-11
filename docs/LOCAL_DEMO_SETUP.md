# Local development after the Supabase Auth migration

The old Clerk demo preparation flow is retired. The local demo database has
been emptied for launch. Do not run seeding tools against the hosted project.
Private recovery backups remain outside the deployment image.

For development checks, use the checked-in unit and browser tests. Playwright
uses mocked identity/API responses and development-only route fixtures; those
shortcuts are compiled out of a production build. Isolated PostgreSQL checks
require an empty disposable database whose name ends in `_test`, explicit
`ARGUS_ENABLE_DESTRUCTIVE_TESTS=I_CONFIRM_DISPOSABLE_DATABASE`, and matching
runtime-role URLs. `scripts/run_launch_checks.py` refuses other targets.

```powershell
.venv/Scripts/python.exe -m pytest api/tests -q
.venv/Scripts/python.exe -m pytest db/tests -q
```

Run browser checks from `frontend` with inert public configuration, so tests
cannot accidentally contact the real authentication project:

```powershell
$env:VITE_SUPABASE_URL='https://abcdefghijklmnopqrst.supabase.co'
$env:VITE_SUPABASE_PUBLISHABLE_KEY='sb_publishable_inert_test_key'
npm run test:e2e
```

Real Google sign-in requires the API database to be the same Supabase project
that issues the session. Migration 027 checks its `auth.sessions` and user
ban/deletion status. Standalone local PostgreSQL has no Auth session rows and
intentionally rejects real login; it must not bypass session revocation.
Use a separate Supabase development project for real-login experiments, with
matching keys, runtime database URLs, exact localhost Auth redirects/CORS and
separate synthetic business data. Do not point destructive tests or seed jobs
at the production project. Keep development signing/encryption keys separate.

See [the production launch handoff](PRODUCTION_LAUNCH.md) for the current free
hosting and Google login configuration.
