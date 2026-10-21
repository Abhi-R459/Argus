# Argus production functional audit

## Production remediation status (21 October 2026, 09:45 IST)

The privacy fixes are live. The Render frontend is deployed from `26dd494`
and the backend from `a11d951`, which includes a production-discovered replay
fix. Ordinary audit-log responses mask employee names, email addresses,
salary amounts, and other sensitive payload keys. Explicit reveal controls
request full payloads and record durable security events. Counterfactual
Replay requires a recorded reveal; evidence JSON, pack, and capsule downloads
also record access. Time Travel's mutation timeline follows its reveal
setting. The HR dashboard uses neutral ledger-count wording.

The 09:45 IST production acceptance pass verified:

- Both Render deployments succeeded on the named commits. The replay fix is
  [backend deployment `dep-dbc3o43ncjis7388o990`](https://dashboard.render.com/web/srv-db5qfenavr4c739nd0q0/deploys/dep-dbc3o43ncjis7388o990), and the privacy UI is
  [frontend deployment `dep-dbc3lcjrjlhs73anbupg`](https://dashboard.render.com/static/srv-db5qfenavr4c739nd0o0/deploys/dep-dbc3lcjrjlhs73anbupg).
- All 15 public deployment checks passed, including API readiness, protected
  routes, security headers, CORS, and frontend routes.
- The signed-in auditor browser displayed `[REDACTED]` for a salary-history
  amount in the ordinary audit log. The Audit Chain reveal control was off by
  default. Counterfactual's new control was off by default and, when selected,
  a real replay succeeded with one event excluded and six applied.
- Supabase recorded a `COUNTERFACTUAL_PII_REVEAL` security event for that replay.
  The deployed HR dashboard asset contains `Audit Ledger Events` and no longer
  contains `Verified Audit Ledger`; the HR role itself was not available for a
  signed-in browser check.
- API tests passed locally (210/210) and the
  [`a11d951` GitHub CI run](https://github.com/Abhi-R459/Argus/actions/runs/39542851877) succeeded.

During acceptance, replay initially returned a generic database-unavailable
response. Supabase logs showed a denied `employees` table read by the
`compliance_auditor` role. The endpoint had caught that read error without
rolling back its transaction. Commit `a11d951` validates personnel through
the permitted audit trail instead. The successful browser replay and recorded
security event confirm the production fix.

The observations below were captured before this remediation and remain a
historical record of the original audit.

Synthetic production history, external-anchor lag, witness quorum, exact
deployed commit, and backup/restore rehearsal still require operational action.

**Observed:** 21 October 2026, about 08:40–08:44 IST

**Production UI:** https://argus-frontend-0i6n.onrender.com

**Production API:** https://argus-backend-u0i3.onrender.com
**Source inspected:** local `codex/production-launch` checkout at `48484a4a8c05b1cb4451ad5975c677271a4a23ff`. The live deployment's exact commit was not independently established. The older launch handoff names `2f1dd71`; therefore code observations below describe the checked-out implementation and are not proof that every line is deployed.

## Executive assessment

The available auditor session loaded the production application, and its main investigation workflows returned real data. The API passed all 15 public deployment checks. A full browser-initiated verification reported **212 entries scanned, four of four checks passed, zero anomalies**. Sequence navigation, audit-log filtering, historical reconstruction, counterfactual replay, risk monitoring, analytics, and Merkle proof generation all returned usable results. The UI reported that a full evidence bundle and a selective capsule download started.

This was **not a complete real-world production acceptance**. The HR role and personnel-writing workflows could not be exercised with the available auditor account; fresh Google sign-in and sign-out were not repeated. No independent restore, key recovery, or evidence-file verification was performed. The earlier privacy disclosure issue was corrected and spot-checked in the 09:45 follow-up above. The 08:40 production snapshot contained 102 synthetic QA employee inserts and 212 permanent audit entries. At that observation the newest two entries were beyond the last external anchor, and no independent witness quorum was configured. These observations are time-bound; check the live overview for current counts and anchor state.

### Severity guide

- **High:** fix before using real personnel information.
- **Medium:** production trust, operations, or user-facing accuracy problem.
- **Low:** smaller product or documentation issue.

## Findings from the pre-remediation observation

The findings below describe the approximately 08:40 IST state unless a later
status is given. They are retained as an incident and acceptance record, not a
claim that every issue remains present in the later deployment. The 09:45 IST
follow-up above confirmed the privacy remediation and successful replay path;
fresh retesting is still needed after later releases.

| ID | Severity | Finding and evidence | Practical consequence / next action |
|---|---|---|---|
| F1 | High at initial observation; remediation verified at 09:45 | **Auditor disclosure controls were inconsistent.** Time Travel initially returned `full_name`, `email`, and `salary` as null and labeled them Restricted, while its timeline showed compensation. Counterfactual Replay displayed full identity and salary without an explicit reveal control. The 09:45 follow-up verified that ordinary audit-log data was masked, explicit reveals were recorded, Counterfactual Replay required a recorded reveal, and evidence JSON/pack/capsule downloads recorded access. Relevant code: `frontend/src/components/auditor/TimeTravelView.tsx`, `frontend/src/pages/auditor/CounterfactualPage.tsx`, `api/routers/audits.py`. | The earlier behavior was corrected in the audited deployment. The browser pass verified the replay control and recorded security event, but not every disclosure path or edge case. Re-run the auditor privacy matrix after later releases. |
| F2 | Medium | **Production contains synthetic test records.** The live analytics page showed 102 employee inserts, 106 salary-history inserts, 212 audit-log inserts, and three checkpoints. The personnel selectors listed `QA Scale ...` roles and a `QA Synthetic Employee ...` record. The 11 October handoff still described an empty hosted database at the time. | Production history contains synthetic QA activity. These records cannot simply be erased without affecting the audit chain. The launch handoff has since been updated to document this dated snapshot. Decide whether this instance remains a demonstration environment before loading real personnel data. |
| F3 | Medium | **The newest events were beyond the external anchor at the 08:40 observation.** The live overview reported a private GitHub anchor dated 15 October, with **two entries since last anchor**. Chain verification passed the configured anchor comparison and the full ledger walk, but the newest two entries had no independently retained anchor commitment. The interface also reported `Independent witness quorum UNVERIFIED`; analytics scored the posture **88/100 UNVERIFIED**. | That observation showed internal consistency and a valid earlier anchor, but not independent rollback protection for the newest two entries. The live anchor may have changed since then; inspect current status. A single private anchor does not provide a multi-witness quorum. |
| F4 | Medium | **Deployment configuration was not fully reconciled during the audit.** The checked-in `render.yaml` described `ANCHOR_STORE=none`, while the live UI reported a private GitHub anchor. The exact deployed source revision and effective Render environment were not proven during that audit. | The launch handoff now records this observed discrepancy. Recheck the effective Render configuration and deployed source commit before relying on the runbook. Do not place credentials in documentation. |
| F5 | Medium at initial observation | **HR dashboard wording could overstate verification.** The initial source rendered `Verified Audit Ledger`, `Cryptographically Sealed`, and `Chain Intact` from dashboard statistics rather than a fresh verifier run. The 09:45 deployment check confirmed the asset used neutral `Audit Ledger Events` wording. The HR role itself was not available for a live browser check. | The deployed wording was corrected. Confirm the actual HR page and behavior during the next authenticated acceptance pass. |
| F6 | Medium | **Recovery and availability are not demonstrated.** The launch handoff states that the free Supabase tier has no downloadable managed daily backups and that Render Free services can sleep. No independent production backup, restore rehearsal, signing-key recovery, or alerting was demonstrated in the browser audit. | Do not treat successful page loads as disaster-recovery validation. Rehearse restore and key recovery using an isolated copy; define monitoring and incident ownership before real-world HR use. |

## Browser test matrix

“Pass” means the stated behavior was directly visible in the production browser during this audit. It does not imply every edge case or a cryptographic file check passed.

| Area / feature | What it does and live result | Status |
|---|---|---|
| Auditor authentication and workspace | An existing approved Supabase session loaded the auditor portal. Direct navigation to `/hr/dashboard` redirected back to the auditor overview. | **Pass for current session and client role routing**; fresh Google sign-in, expiry, and sign-out not retested. |
| Public deployment/security checks | `scripts/check_live_deployment.py` checked API readiness, both runtime database roles, transport/privacy headers, SPA routes, anonymous and invalid-token rejection, disabled docs, and CORS. All **15/15** passed. | **Pass**. These checks do not prove authenticated HR writes or restore. |
| Integrity overview / verification | “Run Verification” completed across **212 entries** with **zero anomalies** and reported hash-chain continuity, checkpoint event commitments, private GitHub anchor comparison, and checkpoint signatures all passed. | **Pass**, with anchor-lag and witness limitations in F3. |
| Chain explorer | Displayed the latest 20 blocks, hash links and actors. Opening block #212 showed hashes and a field-level payload. Jumping to sequence #210 produced a centered 13-block window. | **Pass** for open and jump. Table/action filters, older-page traversal, keyboard shortcuts, and copy actions were not individually exercised. |
| Audit log | Loaded **212 entries across nine pages**. Filtering by sequence #210 reduced the visible results to that event. | **Pass** for load and sequence filter. Other filters, pagination, and national-ID blind search were not exercised. |
| Time Travel | Selected employee #1, reconstructed its current state and exact initial event, and showed the historical active state versus current inactive state. The main response kept name, email, and salary null without reveal. | **Pass** for reconstruction and redaction of the main response; see F1 for the salary shown in the surrounding timeline. Explicit reveal was not exercised. |
| Counterfactual Replay | Excluding salary event #5 produced a read-only state comparison: annual salary variance ₹200,000, estimated cumulative exposure ₹3,833.07, six events applied and one skipped. | **Pass** for a real replay and result rendering; see F1 for disclosure behavior. Estimate is based on rates and dates, not actual payroll payments. |
| Selective Merkle proof | Generated a proof for sequence #1 enclosed by checkpoint #1 with five leaves and a three-level path. `.arguscap` download reported `Download started: proof_seq1.arguscap`. | **Pass** for proof retrieval and browser download initiation. The downloaded archive was not independently opened or verified against an out-of-band public key. |
| Full evidence export | Selected Signed JSON and `.arguspack`. The JSON request returned to idle without an error; the bundle explicitly reported that the browser download started. | **Pass** for the observed bundle generation path; **inconclusive** for JSON file delivery. File persistence, archive contents, signature verification, and usability on an air-gapped machine were not independently checked. |
| Activity & Risk | Unreviewed tab showed zero. All Flags showed two previously reviewed `salary_change_exceeds_30_percent` flags linked to audit sequences. | **Pass** for listing and filtering. Detection refresh, review, reopen, and review history were not changed/tested on production. |
| System Analytics | After loading, showed PostgreSQL active, 100% cache hit, 13 MB database, audit relation 248 kB, table scan counters, verified role segregation, application auth pass, `pgcrypto` active, tail consistency, and 88/100 unverified score. | **Pass** for data loading. A brief initial `FAIL` label while metrics loaded resolved to `PASS`; final state was used. |
| HR dashboard, directory, employee detail | Current role could not enter the HR portal. Source shows headcount/recent activity, employee search/pagination, detail, profile edit, compensation, and soft deactivation. | **Not live-tested with HR credentials**. |
| Department/role setup and CSV import | Source shows HR creation endpoints and import preview, validation, 20-row atomic batches, and a 100-row UI limit. | **Not live-tested**; these create permanent production records. |
| On-demand checkpoint | Source shows HR can sign all events since the last checkpoint, up to 10,000 entries, and records the action; it does not create an external anchor. | **Not live-tested** with HR credentials. |
| National-ID blind-index search | Source sends the ID in a POST body, computes an HMAC blind index, rate-limits queries, and records search telemetry. | **Not live-tested**; no real identifier was supplied. |
| Diagnostic concurrency lab / adversary CLI | Source gates browser diagnostics to development and disables them in production configuration. The CLI is an out-of-band test utility. | **Intentionally unavailable in production UI**; not a production business feature. |
| Browser errors | The tested auditor tabs recorded no browser console warnings or errors in the inspected period. | **Pass for observed interactions only**. |

## Current implementation and storage map

The browser is a React/Vite single-page application on Render static hosting. It keeps a Supabase PKCE session in browser persistence and attaches the Supabase access token to calls to the Render FastAPI service. Server-side verification checks the Supabase Auth user, verified Google identity, approved email list, and active session. API routing selects separate PostgreSQL connection pools for `hr_admin` and `compliance_auditor`; the database is Supabase PostgreSQL. The frontend uses an in-memory TanStack Query cache partitioned by account.

| Feature / data | Implementation path | Durable storage |
|---|---|---|
| Google login and roles | `frontend/src/components/auth/AuthProvider.tsx`; `api/middleware/supabase_auth.py`; `api/routers/auth.py` | Supabase `auth.users` and `auth.sessions`; Argus `users` profile table. Approved email lists and service secrets reside in Render backend configuration. |
| Departments and job roles | `frontend/src/components/hr/OrganizationSetup.tsx`; `api/routers/dashboard.py` | PostgreSQL `departments` and `roles`. |
| Employee directory and HR edits | `frontend/src/components/EmployeeTable.tsx`, `frontend/src/components/hr/EmployeeSheet.tsx`; `api/routers/employees.py` | PostgreSQL `employees`. Names and email are ordinary columns. National ID and contact info use AES-GCM encrypted envelopes; encryption key is an API secret. Deactivation sets `is_active=false`. |
| Compensation | `api/routers/employees.py`; `db/alembic/versions/001_core_entity_tables.py`; business-rule triggers | PostgreSQL `salary_history` stores amount/effective date. DB triggers enforce rules and append changes to audit history. |
| Employee CSV import | `frontend/src/components/hr/EmployeeImport.tsx`; `POST /api/employees/batch` | Same `employees`, `salary_history`, and `audit_log` tables; each server batch is transactional. CSV text is handled in the browser before submit. |
| Audit chain and risk flags | `db/alembic/versions/002_audit_chain_tables.py`, trigger migrations, `api/routers/audits.py` | PostgreSQL `audit_log` contains sequence, before/after JSON, hashes, actor and severity; `chain_state` tracks the tail; `suspicious_activity_flags` and `suspicious_activity_reviews` retain flags and decisions. Encrypted national-ID/contact fields are redacted in audit payloads. Names, email and salary can exist in business/audit records; ordinary auditor API responses mask them, while supported explicit reveals are recorded as security events. |
| Historical and counterfactual analysis | `api/routers/audits.py`; database reconstruction routine and `db/cli/counterfactual.py` | Results are computed from persisted employee and audit rows. A simulation does not alter those rows. Time Travel views/reveals can add rows to `security_audit_events`. |
| Checkpoints, anchors and proofs | `api/routers/checkpoints.py`, `api/routers/audits.py`, verifier/export modules | PostgreSQL `chain_checkpoints` stores signed hashes, Merkle roots and signatures; `checkpoint_schedule_settings` stores the HR-selected automatic interval. The Ed25519 signing key is mounted as a backend secret file. Sanitized anchor records are stored separately in a private GitHub repository and are published by an operator after checkpoint creation; this does not happen automatically. No live witness quorum was observed. Export bundles are generated in memory and sent as downloads. |
| Engine metrics | `GET /api/analytics/system-metrics` | Read from PostgreSQL statistics views; the score is a derived display value, not a durable certification. |
| Backups | Schema has a `backups` metadata table, but the production backup/restore process was not demonstrated. | Separate off-service copies and key backups are required for recoverability. |

## Validation limits and next acceptance pass

The existing auditor browser session was the only live role available. An HR session is required to exercise dashboard counts against the directory, department/role creation, employee creation/edit/deactivation, salary rules, import, checkpoint creation, and HR sign-out. Those actions would permanently change the production audit history, so the complete write-path acceptance should run with synthetic records in an isolated staging database, then use a narrow, preplanned real-account smoke check on production. Fresh Google OAuth, token refresh/revocation, account ban/deletion, national-ID search, risk review mutations, export-file verification, and disaster recovery also remain unproven by this browser pass.

**Suggested order:** resolve F1; decide whether the current production instance is a demo or real personnel environment (F2); reconcile live deployment and anchoring documentation (F3–F4); fix the HR dashboard integrity wording (F5); then run a staging acceptance matrix with both roles and a restore/key-recovery rehearsal (F6). Re-run the 15 public checks and the explicit live verifier after any release.
