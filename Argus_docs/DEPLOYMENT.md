# Deployment and administration

The current release uses Supabase Google Auth, a Render static frontend,
one Render Free Docker API, and the existing Supabase Free PostgreSQL project.
Use the reviewed `codex/production-launch` branch and the updated `render.yaml`.
No paid disk, worker, database, authentication add-on or trial is required.

Follow [the launch handoff](../docs/PRODUCTION_LAUNCH.md) and
[operations guide](../docs/PRODUCTION_OPERATIONS.md) for verified configuration,
secret files, exact redirect/origin settings, free-plan limits and release checks.
The examples are templates and must not be deployed unchanged.

Roles come from the API's `HR_ADMIN_EMAILS` and `COMPLIANCE_AUDITOR_EMAILS` after
verified Google sign-in. User-editable metadata never grants permissions.
`POST /api/auth/sync` is an authenticated application call, not a Clerk webhook.
Do not grant runtime access to migration administrator credentials.
