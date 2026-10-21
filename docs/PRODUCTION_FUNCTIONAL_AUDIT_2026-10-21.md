# Argus production functional audit

## Local remediation status (21 October 2026)

The source changes after this live audit mask names, email addresses, salary
amounts, and other sensitive audit payload keys in ordinary audit-log and
chain responses. Explicit reveal controls now request full payloads, with
durable security events. Counterfactual Replay requires a recorded reveal;
evidence JSON, pack, and capsule downloads also record access. Time Travel's
mutation timeline follows its existing reveal setting. The HR dashboard now
uses neutral ledger-count wording. These changes passed the local API suite
and frontend build, but **were not deployed or re-tested in production** when
this note was written. The production observations below describe the live
version before remediation.

Synthetic production history, external-anchor lag, witness quorum, exact
deployed commit, and backup/restore rehearsal still require operational action.

**Observed:** 21 October 2026, about 08:40–08:44 IST

**Production UI:** https://argus-frontend-0i6n.onrender.com

**Production API:** https://argus-backend-u0i3.onrender.com
**Source inspected:** local `codex/production-launch` checkout at `48484a4a8c05b1cb4451ad5975c677271a4a23ff`. The live deployment's exact commit was not independently established. The older launch handoff names `2f1dd71`; therefore code observations below describe the checked-out implementation and are not proof that every line is deployed.

## Executive assessment

The available auditor session loaded the production application, and its main investigation workflows returned real data. The API passed all 15 public deployment checks. A full browser-initiated verification reported **212 entries scanned, four of four checks passed, zero anomalies**. Sequence navigation, audit-log filtering, historical reconstruction, counterfactual replay, risk monitoring, analytics, and Merkle proof generation all returned usable results. The UI reported that a full evidence bundle and a selective capsule download started.

This is **not yet a complete real-world production acceptance**. The HR role and all personnel-writing workflows could not be exercised with the available auditor account; the Google sign-in and sign-out flows were not repeated. No independent restore, key recovery, or evidence-file verification was performed. The current privacy disclosure behavior is inconsistent across auditor screens. Production contains 102 synthetic QA employees and 212 permanent audit entries, contrary to the launch handoff's empty-database description. The latest two entries are beyond the last external anchor, and there is no independent witness quorum.

### Severity guide

- **High:** fix before using real personnel information.
- **Medium:** production trust, operations, or user-facing accuracy problem.
- **Low:** smaller product or documentation issue.

## Confirmed findings

| ID | Severity | Finding and evidence | Practical consequence / next action |
|---|---|---|---|
| F1 | High | **Auditor disclosure controls are inconsistent.** Time Travel initially returned `full_name`, `email`, and `salary` as null and labeled them Restricted. On the same employee's timeline it displayed compensation amounts. Counterfactual Replay displayed the employee's full name, work email, current salary, and comparison salary without an explicit reveal control. In the inspected source, Time Travel writes a `TIME_TRAVEL_PII_REVEAL` or `TIME_TRAVEL_VIEW_REDACTED` security event, while `POST /api/audit-logs/counterfactual` directly returns replay state without an equivalent disclosure event. Relevant code: `frontend/src/components/auditor/TimeTravelView.tsx`, `frontend/src/pages/auditor/CounterfactualPage.tsx`, `api/routers/audits.py`. | An authorized auditor can obtain fields that the Time Travel screen presents as restricted without using its recorded reveal path. Define a single policy for auditor name, email, and compensation access; enforce it in every API response and record disclosures consistently. Test with real role accounts and non-synthetic data in staging. |
| F2 | Medium | **Production contains synthetic test records.** The live analytics page showed 102 employee inserts, 106 salary-history inserts, 212 audit-log inserts, and three checkpoints. The personnel selectors listed `QA Scale ...` roles and a `QA Synthetic Employee ...` record. The 11 October launch handoff says the hosted business tables were empty. | Production history is already populated with QA activity. These records cannot simply be erased without affecting the audit chain. Decide whether this instance is a demonstration environment or a real personnel system; document and segregate the synthetic data accordingly. Update the launch handoff. |
| F3 | Medium | **Newest events lack the separate external anchor.** The live overview reported a private GitHub anchor dated 15 October, with **two entries since last anchor**. Chain verification passed the configured anchor comparison and the full ledger walk, but the last two entries have no independently retained anchor commitment. The interface also reported `Independent witness quorum UNVERIFIED`; analytics scored the posture **88/100 UNVERIFIED**. | Verification shows current internal consistency and a valid earlier anchor, but does not give the newest two entries the same independent rollback protection. Establish an anchor publication schedule and monitor anchor lag. A single private anchor does not provide a multi-witness quorum. |
| F4 | Medium | **Deployment documentation/configuration is stale or drifted.** `docs/PRODUCTION_LAUNCH.md` and the checked-in `render.yaml` describe `ANCHOR_STORE=none`, while the live UI reports a private GitHub anchor. The handoff also describes an empty ledger, while the live one has 212 entries. The exact deployed source revision was not proven during this audit. | Reconcile the live Render configuration, source commit, anchor credentials, and operations documentation before relying on the document as the production runbook. Do not place credentials in the runbook. |
| F5 | Medium | **HR dashboard wording can overstate verification.** In the inspected source, its `Verified Audit Ledger`, `Cryptographically Sealed`, and `Chain Intact` labels are rendered from the dashboard statistics query and do not themselves run the chain verifier. The auditor's explicit verification control does perform the walk. | A count or recent activity feed must not be presented as a fresh integrity verdict. Tie these labels to a timestamped verifier result or use neutral wording. This is a source finding; the HR production screen was unavailable to confirm its deployed appearance. |
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
| Audit chain and risk flags | `db/alembic/versions/002_audit_chain_tables.py`, trigger migrations, `api/routers/audits.py` | PostgreSQL `audit_log` contains sequence, before/after JSON, hashes, actor and severity; `chain_state` tracks the tail; `suspicious_activity_flags` and `suspicious_activity_reviews` retain flags and decisions. Sensitive encrypted fields are redacted in audit payloads, but names/email/salary remain available through relevant audit/replay paths. |
| Historical and counterfactual analysis | `api/routers/audits.py`; database reconstruction routine and `db/cli/counterfactual.py` | Results are computed from persisted employee and audit rows. A simulation does not alter those rows. Time Travel views/reveals can add rows to `security_audit_events`. |
| Checkpoints, anchors and proofs | `api/routers/checkpoints.py`, `api/routers/audits.py`, verifier/export modules | `chain_checkpoints` stores signed hashes, Merkle roots and signatures. Signing key is a backend secret file. The live app reports a private GitHub anchor repository for separately retained anchor records; no live witness quorum was observed. Export bundles are generated in memory and sent as downloads. |
| Engine metrics | `GET /api/analytics/system-metrics` | Read from PostgreSQL statistics views; the score is a derived display value, not a durable certification. |
| Backups | Schema has a `backups` metadata table, but the production backup/restore process was not demonstrated. | Separate off-service copies and key backups are required for recoverability. |

## Validation limits and next acceptance pass

The existing auditor browser session was the only live role available. An HR session is required to exercise dashboard counts against the directory, department/role creation, employee creation/edit/deactivation, salary rules, import, checkpoint creation, and HR sign-out. Those actions would permanently change the production audit history, so the complete write-path acceptance should run with synthetic records in an isolated staging database, then use a narrow, preplanned real-account smoke check on production. Fresh Google OAuth, token refresh/revocation, account ban/deletion, national-ID search, risk review mutations, export-file verification, and disaster recovery also remain unproven by this browser pass.

**Suggested order:** resolve F1; decide whether the current production instance is a demo or real personnel environment (F2); reconcile live deployment and anchoring documentation (F3–F4); fix the HR dashboard integrity wording (F5); then run a staging acceptance matrix with both roles and a restore/key-recovery rehearsal (F6). Re-run the 15 public checks and the explicit live verifier after any release.
