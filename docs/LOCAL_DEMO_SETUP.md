# Local development with Clerk authentication

The old Clerk demo preparation flow is retired. The local demo database was
restored from an isolated recovery snapshot for professor demonstrations. It
is separate from the hosted production database. Do not run seeding, attack, or
destructive test tools against the hosted project. Private recovery backups
remain outside the deployment image.

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
$env:VITE_CLERK_PUBLISHABLE_KEY='pk_test_dGVzdC5jbGVyay5hY2NvdW50cy5kZXYk'
npm run test:e2e
```

The local demo snapshot contains synthetic demonstration data and can differ
from production. Real sign-in requires a Clerk development instance, the API's
matching public verification key and secret key, and exact localhost origin
configuration. The API checks active sessions with Clerk. Use separate synthetic
business data for real-login experiments. Do not point destructive tests or
seed jobs at the production project. Keep development signing and encryption
keys separate.

See [the Clerk production release runbook](CLERK_PRODUCTION_RELEASE.md) for the
current hosting and domain configuration.
