# Product Requirements Document (PRD)

## Project Title
**Argus — A Tamper-Evident, Self-Verifying Audit Trail Engine for PostgreSQL**

---

## 1. Overview

Argus is a security-focused database system that solves a problem most real systems get wrong: **audit logs that claim to record "who did what" but can be silently edited by anyone with sufficient database privilege — including the very administrators the log is supposed to watch.**

Instead of building "yet another app with a database," Argus builds the missing piece: a hash-chained, cryptographically self-verifying audit trail engine for PostgreSQL, demonstrated on top of a small Employee Records Management system (HR records — names, roles, salaries, contact info — the kind of sensitive data insider misuse regularly targets in the real world).

Every sensitive action taken by an HR Admin is logged into an append-only, hash-chained trail. A separate Compliance Auditor role can independently verify — mathematically, not by trust — whether that trail has been tampered with, up to and including a database superuser directly editing historical rows. Combined with lightweight external anchoring (Section 5.5), the system also catches the more sophisticated case of a privileged attacker editing an entry **and** recomputing every hash after it to restore internal consistency.

**A note on scope:** the Employee Records module exists to generate realistic data changes to audit — it is deliberately kept small. The hash-chained audit trail, the role-separation model, and the verification engine are the actual point of this project and the primary basis for evaluation, not the CRUD application sitting on top of them.

---

## 2. Problem Statement

This is a validated, current, and largely unsolved gap — not a hypothetical one:

- The majority of real-world data breaches involve a human element, including malicious insiders and privileged-credential abuse — this is one of the most common breach causes tracked industry-wide today.
- Almost every "audit log" in production systems is just a regular database table. Anyone with enough privilege (a DBA, a compromised admin account, a rogue employee) can quietly `UPDATE` or `DELETE` rows in it, and there is no way to later prove that happened.
- **Amazon built exactly this as a managed product (QLDB)** — an immutable, cryptographically verifiable ledger database — and discontinued it, telling all their customers to migrate to plain Aurora PostgreSQL, which does **not** natively retain tamper-evident history. If you need what QLDB provided, you now have to build it yourself.
- **Microsoft's SQL Server/Azure SQL "Ledger" feature** does solve this properly — but it's proprietary and locked to Microsoft's database engine.
- **PostgreSQL's own official audit extension, pgAudit**, explicitly documents that its logging is best-effort and not transactional — meaning committed changes can go unlogged, and it makes no tamper-evidence guarantee at all.
- **pgMemento**, the most widely used Postgres audit-trail extension, provides excellent version history — but protects its log only through database permissions, not cryptographic proof. Anyone with sufficient access can still rewrite history undetected.
- The only real fix people currently use in production is bolting on an entirely separate, purpose-built database (e.g., immudb) alongside Postgres — adding a second system just to get the one property Postgres lacks natively.

In short: the "real" solution was tried, killed, and never rebuilt as an open, database-native tool. Developers are still hand-rolling ad-hoc versions of this in blog posts as recently as this year, with no shared standard to reach for.

---

## 3. Objectives

The system should:

- Maintain an append-only, hash-chained audit trail of every sensitive action on watched tables, such that altering any past entry is mathematically detectable
- Guarantee this holds **even against a database superuser or DBA-level attacker** who edits a single historical entry — not just against the application layer
- Additionally, via lightweight external anchoring, detect the harder case of an attacker who edits an entry *and* recomputes all subsequent hashes to hide the edit — a limitation of hash-chaining alone that the PRD explicitly designs around rather than glosses over
- Provide an independent verification tool that walks the chain and proves (or disproves) integrity, and pinpoints the exact entry where tampering occurred if it did
- Enforce least-privilege separation between the role being watched (HR Admin) and the role doing the watching (Compliance Auditor)
- Encrypt sensitive fields at rest
- Demonstrate all of the above via a live, deliberate "self-attack" — not just claim it in a report

---

## 3.1 Project Proposal Summary

This is a faculty-approved database application in the employee-records and compliance domain. The primary deliverable is a working PostgreSQL-backed application and verification tool, not a general-purpose HR suite.

**Scope:** employee CRUD, a normalized relational schema, database-enforced audit logging, independent verification, two-role access control, search/filtering/pagination, a responsive dashboard, backup/restore evidence, Docker packaging, and a deployed demonstration.

**Team:** Abhinav owns the database core, security mechanisms, and verifier. Nidhurshek owns the FastAPI integration, React dashboards, managed authentication integration, and deployment. Both developers own testing, documentation, and the final demonstration.

**Major deliverables:**

1. ER diagram, relational schema, normalization proof, constraints, indexes, and data dictionary
2. PostgreSQL schema/migrations with CRUD, joins, aggregate queries, views, a stored procedure, triggers, and transaction demonstrations
3. FastAPI + React application with Clerk authentication, local database RBAC, search, filtering, pagination, validation, and exception handling
4. Standalone verifier, signed checkpoints, external-anchor adapter, attack-demo scripts, and benchmark results
5. Docker Compose setup, Docker Hub image(s), `pg_dump`/`pg_restore` evidence, private GitHub repository, and live deployment URL

The security-critical mechanisms remain project-owned. Commodity concerns—identity management, password handling, UI primitives, client validation, and deployment hosting—use established free software or services instead of being reimplemented.

---

## 4. Target Users (Two Roles, Single `users` Table)

**A required design correction, made explicit here:** per course requirements, all application users are maintained in **one `users` table** distinguished by a `role` column (`hr_admin` or `compliance_auditor`) — never separate tables per role. This sits *above* Argus's existing database-role layer, not in place of it:

- **`users`** (application layer) — local identity and authorization data: Clerk subject, name, email, and `role`. Clerk authenticates the person; this table determines Argus access.
- **Postgres `hr_admin` / `compliance_auditor`** (database-connection layer, `CREATE ROLE`) — what a database connection is allowed to do, enforced by Postgres itself regardless of application code. When a `users` row with `role = 'hr_admin'` logs in, the backend opens its DB connection *as* the Postgres `hr_admin` role.

This is deliberately **two layers, not one**: the `users` table satisfies the standard RBAC pattern most projects stop at; the Postgres role layer is Argus's own additional, database-native enforcement underneath it. Losing either layer would either violate the course requirement (no `users` table) or drop Argus's core differentiator (privilege enforced only in application code, not the database).

### HR Admin (the "watched" role)
- Authenticates through Clerk; the verified Clerk subject maps to a local `users` row with `role = 'hr_admin'`
- Create, update, and deactivate employee records
- View all employee data
- Cannot read, modify, or delete anything in the audit trail — not even their own entries
- Cannot disable logging (enforced at the database role level, not just in application code)

### Compliance Auditor (the "watching" role)
- Authenticates through Clerk; the verified Clerk subject maps to a local `users` row with `role = 'compliance_auditor'`
- Read-only access to the audit trail (never to raw employee data itself, only to the log of changes)
- Runs the verification tool to confirm the chain's integrity
- Cannot modify employee records or the audit trail in any way — a pure observer, so their own access can't be the attack vector

**Note on terminology — three things now share the word "role":** `employees.role_id` (an employee's job title, e.g. "Software Engineer" — pure business data), `users.role` (system permission: `hr_admin`/`compliance_auditor`), and PostgreSQL `CREATE ROLE hr_admin` (a database connection credential). Same word, three layers — flagged explicitly so it's never a source of confusion in the report or viva. The application role is read from the local database after Clerk token verification; it is never trusted from a client-provided field.

---

## 5. Core Modules

### 5.1 Watched Data Layer
- **`users`** — local application identities linked to Clerk by `clerk_user_id`, with name, email, `role`, and active status. Clerk remains the authentication source of truth; Argus stores the minimum local data needed for RBAC and audit attribution
- **`departments`** — a small lookup table containing department names that `roles` references. Department-head assignment is out of scope for this course project, avoiding a circular employee/department dependency
- A small Employee Records schema: `employees`, `roles` (job title, references `departments`), `salary_history`, contact info
- Sensitive fields (e.g., salary, national ID/contact info) encrypted at rest using `pgcrypto`

### 5.2 Hash-Chained Audit Trail
- An **`AFTER INSERT/UPDATE/DELETE`** trigger on every watched table captures the event after the row operation and its constraints succeed, but before the surrounding transaction commits. PostgreSQL atomicity guarantees that the data change and its audit entry are both persisted or both rolled back — never a `BEFORE` trigger, since the log must reflect a successful row operation, not what was merely attempted
- Each log entry stores: a monotonic `sequence_id`, actor, action, table/row affected, old value, new value (as `JSONB`), timestamp, and a **SHA-256** hash (via `pgcrypto`'s `digest()` function) computed over all of the above **plus the hash of the previous entry** — so altering any past row invalidates every hash that follows it
- Each log entry also stores a nullable `employee_id` foreign key for employee-related events. This supports indexed time-travel reconstruction without relying on a polymorphic JSONB lookup
- Sensitive values are redacted or masked in `old_value`/`new_value`; the audit log must not become an unencrypted copy of national IDs or contact information. Full sensitive before/after values are out of scope unless separately encrypted
- A B-tree index is created on `audit_log(sequence_id)` and `audit_log(timestamp)` specifically to keep the verifier's sequential range scans fast as the log grows (Module 4: indexing/access methods)
- A **composite B-tree index on `audit_log(employee_id, timestamp)`** is also required — without it, the time-travel reconstruction (Section 5.8) degrades to a linear scan per employee instead of the logarithmic lookup its complexity claim (Section 16.5) depends on
- The log table is append-only in practice: the application role only has `INSERT`/`SELECT` privileges on it; `UPDATE` and `DELETE` are revoked entirely, even from the HR Admin application role
- Each entry also carries a **severity** (`INFO` / `WARNING` / `CRITICAL`), assigned by action type at insert time (e.g., deactivating an employee is `CRITICAL`, a phone-number change is `INFO`) — trivial to add, and lets the Compliance Auditor filter to what matters instead of scrolling every row

### 5.3 Verification Engine
- A standalone Python tool (independent of the web app) that reads the chain and recomputes every hash to confirm whether it matches what's stored
- Reads the log in **paginated, ordered chunks** via keyset pagination (`WHERE sequence_id > last_checked ORDER BY sequence_id LIMIT N`, not `OFFSET`) rather than a single massive `SELECT *`, so verification stays efficient as the log grows (Module 4: query processing/optimization)
- If tampering is found, it reports the **exact entry where the chain first breaks**, and continues past that point to identify the full extent of the divergence rather than simply halting
- Separately, compares the current chain tail hash against the most recent externally anchored value (Section 5.5). A clean chain with a tail that *doesn't* match the last anchor reveals the harder attack: someone tampered with an entry and successfully recomputed every hash after it

### 5.4 Concurrency-Safe Chain Writes
- A single-row `chain_state` table tracks the current tail hash and sequence number. Every trigger-driven log write first acquires that row via **`SELECT ... FOR UPDATE`** — a row-level exclusive lock — before computing the next hash, so two concurrent transactions can never both read the same "previous hash" and append conflicting entries
- This is a direct, concrete application of lock-based concurrency control (Module 6), rather than just describing Two-Phase Locking in the abstract: the lock is acquired before the critical read (the current tail), held through the write (the new entry), and released at commit — textbook 2PL behavior applied to a real problem
- Postgres advisory locks were considered as an alternative but not used as the primary mechanism, since `FOR UPDATE` maps directly onto the row-level locking protocols taught in the syllabus, making the implementation easier to explain and justify in a viva

### 5.5 External Anchoring (Core Requirement, Not Stretch)
- **Why this had to move from "stretch goal" to core:** a hash chain alone only proves *internal* consistency. A sophisticated attacker with superuser access could edit a historical entry and then recompute every hash after it, producing a chain that is perfectly self-consistent and would pass a chain-only check. Without an anchor, the "tamper-evident even against a superuser" claim would only be half-true — this is a known limitation of hash-chaining discussed in current research on the topic, not something we can gloss over
- **Implementation (kept intentionally lightweight):** the verifier writes a signed checkpoint through an `AnchorStore` adapter. Local development uses a protected file outside the demo's `hr_admin` persona. The deployed demonstration uses a separate private GitHub repository or equivalent external store, with its token and signing key held only by the verifier environment
- The external store is deliberately outside PostgreSQL and outside the application database roles. The project threat model excludes compromise of the external store and its credentials; that limitation is stated explicitly rather than implying that a local file is durable cloud storage
- The verifier's tail-vs-last-anchor comparison (Section 5.3) is what actually exercises this: an attacker who edits history and recomputes forward will still be caught the next time the current tail is compared against a previously anchored value that predates the tamper

### 5.6 Dashboards

**Compliance Auditor Dashboard (the primary demo surface)**
- A status banner reflecting the verifier's last run: a clear "Verified — N entries, no tampering" state, or a flagged state naming the exact entry where divergence begins
- A **visual chain view** — sequential linked blocks showing truncated hashes and the link between each entry and the one before it, with the broken link highlighted the moment tampering is detected. This turns the verifier's output from a terminal printout into something a non-technical viewer (or a professor skimming quickly) can understand at a glance
- Anchor status: last anchor timestamp and whether the current tail hash matches it — this is where the recompute-and-hide attack (Section 6, scenario 5) becomes visible even when the chain view itself looks clean
- A filterable audit log table (by actor, action, table, date range, and severity — see Section 5.2), with **free-text search** (actor name, table name) and **UI-level pagination** — distinct from the verifier's internal keyset pagination (Section 5.3), this is ordinary paged results for a human browsing the log, not an optimization
- A "Run Verification" control that triggers the CLI tool live and updates the dashboard with the result
- **Diff viewer:** clicking a log entry shows its `old_value` vs `new_value` side by side with changed fields highlighted, rather than raw `JSONB` — makes the trail actually inspectable, not just technically complete
- **Activity & risk panel:** changes-by-role/actor today, most-sensitive-field changes, and any flagged suspicious patterns (Section 5.9) — makes the least-privilege model visible instead of implied by code
- **Query/indexing panel:** verification runtime and rows scanned, with a toggle to compare against an unindexed run — turns Module 4's indexing benefit into something seen, not just claimed
- **Security posture panel:** a compact summary of which columns are encrypted, current role grants, and revoked privileges
- **Concurrency lab:** a control that fires two simultaneous updates to the same record and displays the resulting chain ordering, so Section 5.4's concurrency-safety claim has a live, repeatable demo rather than only a manual test run

**HR Admin Dashboard**
- Standard employee CRUD screens (create/update/deactivate records), with **search by name/email** and **paginated results** — the same explicit requirement as the audit log table above, applied to the employee list
- A small "your recent actions" widget, mainly to make clear during the demo that these actions are the ones being logged

This module doesn't add new scope beyond what Section 10 already plans (React + Tailwind) — it's the difference between building that frontend as plain forms versus building it as a dashboard layout that actually shows the project's core mechanism working, which matters for how the attack demo (Section 6) lands live.

---

### 5.7 Business Rule Enforcement (Constraints, Not Just Code)
- A small, deliberately limited set of business rules enforced as **database constraints and triggers**, not application-side checks, so they hold even if the API is bypassed entirely:
  - A single salary update cannot decrease pay by more than 30% in one transaction (enforced via a trigger comparing old vs new row values, since a plain `CHECK` constraint can't see the prior value)
  - `national_id` cannot be modified once set
  - An HR Admin cannot modify their own salary record
- Kept to 2-3 concrete rules rather than a general-purpose "policy engine," so effort stays proportional to the timeline while still demonstrating that integrity constraints (Module 2/3) can enforce real business logic, not just structural correctness
- **Rejected attempts are not written by the rejecting trigger transaction:** PostgreSQL rolls back all writes in a transaction that raises an exception. If time permits, the API records failed authorization attempts in a separate `security_events` transaction; this is a supplementary signal, not part of the atomic success audit trail and not a code-independent trigger guarantee

### 5.8 Time-Travel Queries
- Since every change already carries old/new values and a timestamp, the system can answer "what did this employee's record look like at time T" by walking the log backward from the most recent entry before T — no separate temporal-tables extension needed
- Exposed in the Compliance Auditor Dashboard: pick an employee and a timestamp, see the reconstructed record as of that moment
- Low incremental cost given the existing schema already stores exactly what this needs; demonstrates a real enterprise feature (Oracle Flashback Query, SQL:2011 temporal tables) using only the audit trail already built for security purposes

### 5.9 Suspicious Activity Detection (Plain SQL, Not ML)
- A small set of pattern queries flag potentially suspicious behavior directly from the audit log, using aggregate and window functions only:
  - The same actor making an unusually high number of changes within a short window
  - The same record modified more than once within a short window
  - Changes occurring outside a defined normal-hours window
- Flagged results are persisted in a **`suspicious_activity_flags`** table (referencing the triggering `audit_log` entry, and optionally the `users` row that later reviewed it), rather than recomputed from scratch on every dashboard load — this also gives the Compliance Auditor a durable "reviewed / not yet reviewed" state per flag
- Surfaces as a filter in the dashboard's activity panel (Section 5.6) — a few well-chosen `GROUP BY`/window-function queries plus one small table, which is the right scope for a DBMS course rather than a manufactured "detection engine"

### 5.10 Checkpoint Signing (Authenticity, Not Just Integrity)
- **The distinction this adds:** a hash proves data hasn't changed; it doesn't prove who produced it. A digital signature adds authenticity and non-repudiation — someone who could forge a plausible hash still cannot forge a valid signature without the private key
- The verifier uses Python `cryptography` for Ed25519 signing. The verifier-owned signing path keeps its private key outside PostgreSQL and the HR database role. **Current implementation note:** the HR-only `POST /api/checkpoints/create` route can load a local signing key into FastAPI in development/demo so an HR admin can seal pending events on demand. The user receives the signed checkpoint result, not private-key bytes, but API compromise can expose this local key. The route fails closed in production until a managed signing adapter is integrated. Automatic checkpoints remain separate from this user-triggered action, and a signature does not itself create an external anchor.
- On verification, the tool checks the signature against the known public key before trusting an anchor value — so someone who gained write access to the external anchor store still cannot plant a convincing fake entry without the private key
- Directly strengthens the Section 6 threat model: the anchor was already outside `hr_admin`'s reach; signing makes it forgery-resistant even if that boundary were somehow crossed

### 5.11 Backup Integrity Verification (Lightweight)
- Each database backup (`pg_dump` output) is hashed at creation time, and that hash is stored in a **`backups`** table (optionally referencing the active `chain_checkpoints` row at backup time), rather than left implicit
- Before any restore, the backup file's hash is recomputed and compared — a corrupted or tampered backup is caught before it's trusted, not after
- Deliberately scoped to hashing and verification only, not a full automated recovery pipeline (see Section 14) — keeps the Module 5 (recovery) tie concrete without committing to real backup/restore orchestration

### 5.12 Immutable Evidence Export
- A single export function generates a compliance summary (entry count, verification result, current tail hash, last signed checkpoint, timestamp) as signed JSON. A human-readable PDF is optional and rendered with established free tooling (Jinja2 + WeasyPrint), not a custom PDF engine
- A tangible artifact for the demo — something handed to a professor or auditor as proof, not only a live on-screen result
- Builds directly on Section 5.10's signing key; no new cryptographic infrastructure required

### 5.13 Hybrid Verification Strategy (Parallel Checkpoint Verification)
- **This is the project's strongest genuine novelty lever** — everything else in Section 5 is a correct application of known techniques (hash chains, RBAC, encryption); this is an actual proposed-and-evaluated systems contribution
- **Stated as a hypothesis, not an assumed result:** *checkpoint-parallelized verification reduces wall-clock verification time relative to a naive sequential walk, with speedup approaching the theoretical O(n/P) bound (Section 16.5) as checkpoint segment count c grows relative to worker count P.* Section 16.8 exists specifically to test this — not to assume it holds
- Because checkpoints (Section 9) already partition the chain into segments, each segment can be verified independently once its starting hash (the prior checkpoint) is known — the segments don't need to be walked strictly sequentially from genesis
- The verifier first fetches checkpoint boundaries, then verifies segments in parallel (e.g., Python `multiprocessing` or multiple async connections), rather than one long sequential walk
- **Adaptive checkpoint intervals** (adjusting the interval based on write volume) is a natural extension of this, but is kept as an **optional stretch goal, not a commitment** — it adds a real design/tuning problem (defining and empirically validating the adaptation rule) on top of everything else already planned

### 5.14 Database Views (Course Requirement)
Two views, each backing a real dashboard panel rather than existing to check a box:
- **`v_employee_directory`** — joins `employees` + `roles` + `departments` + each employee's latest `salary_history` row. Backs the HR Admin Dashboard's employee list directly, so the application never repeats this join in code
- **`v_compliance_overview`** — joins `chain_state` + the latest `chain_checkpoints` row + the latest `backups` verification result + a count of unreviewed `suspicious_activity_flags`. Backs the Compliance Auditor Dashboard's status cards (Section 5.6) in one query instead of four

### 5.15 Stored Procedure (Course Requirement, Distinct from Triggers)
The course rubric requires a stored procedure separately from triggers. PostgreSQL functions are the right interface for returning a reconstructed record, so `reconstruct_employee_state(employee_id, as_of_timestamp)` is implemented as a callable function. A separate PostgreSQL procedure, `CALL refresh_suspicious_activity_flags()`, performs the persisted suspicious-activity scan. The API invokes both through the approved raw-SQL boundary.

---

## 6. Security Architecture (Core Differentiator)

| Concern | Mechanism | Layer |
|---|---|---|
| Silent tampering with history | Hash-chained log entries; any past edit invalidates all later hashes | Database |
| DBA/superuser rewriting a single log entry | Hash-chain verification, run independently of the database session that would do the tampering | Database |
| DBA/superuser rewriting an entry *and* recomputing the chain after it | External anchoring — the recomputed chain is internally consistent but no longer matches a previously anchored tail hash | Database + external |
| Forged or planted anchor entry | Checkpoint signing (Section 5.10) — an anchor value without a valid signature from the known key is rejected | External |
| Privilege escalation | Two-layer RBAC: `users.role` at the application layer, plus two distinct Postgres roles (`hr_admin`, `compliance_auditor`) via `GRANT`/`REVOKE` at the connection layer; auditor has zero write access anywhere | Application + Database |
| Incomplete/lost audit entries | Log write and triggering data change happen in the same transaction, so both commit or neither does | Database |
| Sensitive data exposure | `pgcrypto` encryption on sensitive columns plus redacted audit payloads | Database |
| SQL Injection | Parameterized queries via SQLAlchemy exclusively | Application + Database |

### Planned "Attack Demo" (live proof, not just claims)
1. Log in as `hr_admin`, make a normal series of changes (create/update/deactivate employee records) → verifier confirms the chain is clean
2. Directly connect as a database superuser and edit a historical log row (e.g., change a salary-change entry's old value) → run the verifier again → it correctly identifies that exact entry as the point of divergence, not just "somewhere is broken"
3. Attempt to `UPDATE`/`DELETE` a log row using the `hr_admin` application role → rejected outright by revoked privileges, before it could even happen
4. Fire two concurrent transactions that both modify watched data at the same instant → confirm the resulting chain is still correctly ordered and unbroken, proving the concurrency-safety design works under real contention
5. **The harder case:** as superuser, edit a historical entry *and* manually recompute every hash after it so the chain is internally self-consistent again → a chain-only verifier check would report "clean," but comparing the current tail against a previously recorded anchor value reveals the mismatch — demonstrating concretely why anchoring, not just hashing, is necessary
6. Attempt to insert a fake anchor entry (a plausible hash without a valid signature) into the external anchor store → verifier rejects it as unsigned, distinguishing a genuine checkpoint from a planted one

---

## 7. Business Workflow

**Normal Operation**
HR Admin performs an action on employee data → trigger fires within the same transaction → hash-chained log entry appended → both commit together or neither does

**Verification Flow**
Compliance Auditor runs the verifier → tool walks the chain from genesis to tail, recomputing hashes → reports "chain intact" or the exact point of divergence

**Attack Scenario (demo)**
Privileged attacker edits a historical log entry directly → next verification run detects and localizes the tampering → auditor is alerted to exactly which record and when it was altered

---

## 8. Functional Requirements

The system shall:
- Log every INSERT/UPDATE/DELETE on watched tables automatically via triggers, not application code
- Make the audit log append-only at the database privilege level, including against the application's own admin role
- Detect any modification to historical log entries via hash-chain verification
- Encrypt at least the most sensitive employee data columns at rest
- Enforce two roles with clearly different, least-privilege database permissions
- Keep the audit log write and the data-change write atomic (same transaction)
- Present verification results, chain status, and anchor status through a visual dashboard rather than requiring the Compliance Auditor to read raw CLI output
- Enforce a small set of business rules as database constraints/triggers, independent of the application layer
- Support reconstructing an employee record's state as of any past point in time, using only the existing audit trail
- Flag suspicious activity patterns (rapid bulk changes, repeated changes to the same record, off-hours activity) via SQL queries
- Sign periodic checkpoints so anchored values are authenticated, not just hashed
- Authenticate users through Clerk and maintain all application users in a single local `users` table distinguished by a `role` column — never separate tables per role
- Support search and paginated results on both the employee list and the audit log table, distinct from any internal query-optimization pagination
- Provide at least one database view backing a real dashboard query, a callable time-travel function, and at least one real stored procedure invoked directly (not merely a trigger's backing function)

---

## 9. Non-Functional Requirements

**Performance:** Verification of the full chain should complete in well under a few seconds for the demo dataset size
**Reliability:** No log entry should ever be lost or duplicated relative to the data change it records
**Security:** Append-only enforcement via `REVOKE`, encrypted sensitive columns, least-privilege roles, injection-resistant queries
**Scalability:** A checkpoint is recorded every **25 entries** (a small interval chosen deliberately so it actually fires and is demoable against this project's realistic demo dataset size, rather than a production-scale interval like 10,000 that would never trigger during the demo). Each checkpoint stores a "trusted hash state" so the verifier can, if desired, resume from the latest checkpoint instead of re-walking the entire chain from genesis — the same principle production systems use at larger scale, just calibrated to be visible here

---

## 10. Technology Stack

- **Backend:** FastAPI (Python)
- **ORM / DB Access:** SQLAlchemy 2 (async), Alembic, Pydantic, parameterized queries throughout
- **Database:** PostgreSQL — with `pgcrypto` (SHA-256 hashing via `digest()`), `JSONB`, `AFTER` triggers, B-tree indexes, `FOR UPDATE` row-level locking, and strict role-based `GRANT`/`REVOKE`
- **Verification Tool:** Standalone Python CLI, independent of the web app's own database session/credentials; `cryptography` supplies established Ed25519 primitives
- **Frontend:** React + Vite + Tailwind CSS; Clerk's React components, React Hook Form, Zod, and TanStack Query provide established UI/auth/form/data primitives
- **Authentication:** Clerk Hobby plan for managed login/logout, OAuth, password handling, and session tokens; Argus retains local authorization in `users.role`
- **Migrations:** Alembic
- **Version Control:** Git + GitHub
- **Testing / CI:** pytest, pytest-benchmark, Playwright, and GitHub Actions — free automated tests and CI/CD target the course bonus without altering the security model
- **Deployment plan, not current deployment status:** Docker Compose locally was the intended development environment; free hosted targets were considered for React, FastAPI, and PostgreSQL. The verified walkthrough currently uses isolated local Docker Compose and Clerk Development. Do not describe the free hosted stack as deployed; see `docs/LOCAL_DEMO_SETUP.md`.
- **External anchor:** local protected file for development and a separate private GitHub repository (or equivalent free external store) for the deployed verifier; the anchor adapter is project-owned, but the storage protocol is not
- **Framework note:** the professor's examples list Django and Flask for Python but do not prohibit FastAPI. Confirm FastAPI with the instructor before implementation; the database design remains portable to Flask if required

---

## 11. Curriculum Mapping Matrix (BCSE302L)

A quick-reference table mapping Argus's features directly to the course's syllabus modules, so alignment is explicit rather than left for a grader to infer.

| Syllabus Module | Argus Feature |
|---|---|
| Module 2: Relational Model & ER Modeling | Full ER design for employees/roles/salary_history/audit_log/chain_state; keys and integrity constraints |
| Module 3: Relational Database Design | Naive "before" schema → normalized (3NF/BCNF) "after" schema, with anomalies explicitly identified and removed |
| Module 4: Physical Design & Query Processing | B-tree indexes on `audit_log(sequence_id, timestamp)`; keyset-paginated verifier queries instead of full-table scans |
| Module 5: Transaction Processing & Recovery | Atomic log-write + data-write in a single transaction; discussion of durability and why partial commits would break the chain |
| Module 6: Concurrency Control | Row-level `SELECT ... FOR UPDATE` locking on the `chain_state` row, directly implementing 2PL-style locking to serialize chain writes |
| Module 7: NoSQL Database Management | `JSONB` storage for old/new row values; explicit discussion of why this data is semi-structured rather than forcing it into rigid columns |
| Course Outcome 5 (unstructured data) | Same `JSONB` usage above, framed as the course's required treatment of unstructured/semi-structured data within a relational system |
| Module 2/3: Integrity Constraints (extended) | Business rule enforcement (Section 5.7) via trigger logic — salary-change caps, immutable `national_id`, self-modification block |
| Module 4: Query Processing (extended) | Time-travel reconstruction and suspicious-activity pattern queries (Sections 5.8, 5.9), both built from aggregate/window functions over the existing log |
| Beyond-syllabus security depth (Cybersecurity category) | Checkpoint signing (Section 5.10) — the hash-vs-signature distinction isn't a named syllabus topic, but directly serves the project's declared Cybersecurity form category |

---

## 12. Database Concepts Demonstrated (Detail)

- ER modeling and normalization (employee/role/salary-history schema)
- Triggers for automatic, code-independent audit logging (Module 6)
- Transactions and atomicity: log write and data write must commit together (Module 5)
- Concurrency control: serializing hash-chain writes correctly under simultaneous transactions via row-level `FOR UPDATE` locking (Module 6)
- Role-based privilege separation via `GRANT`/`REVOKE`, least privilege in practice, not just in theory
- `JSONB` for flexible old/new value storage (Module 7 / NoSQL tradeoff discussion)
- Recovery/durability concepts: why the log write must be part of the same transaction as the data write (Module 5)
- Indexing and query optimization: B-tree indexes and keyset pagination for efficient chain verification at scale (Module 4)
- Constraints and triggers enforcing real business rules, not just structural integrity (Module 2/3, extended)
- Time-travel-style reconstruction from historical log data, and pattern-based anomaly queries using aggregate/window functions (Module 4, extended)

---

## 13. Planning Sequence

1. Finalize this PRD
2. Define user stories for both roles
3. Design an ER diagram and data dictionary for all ten tables: users, departments, roles, employees, salary_history, audit_log, suspicious_activity_flags, chain_state, chain_checkpoints, and backups
4. Normalize schema, define constraints and roles/RLS-adjacent privilege separation
5. Implement the hash-chaining trigger logic in PL/pgSQL, using `FOR UPDATE` on `chain_state` for concurrency-safe writes
6. Build the standalone verification CLI, including keyset-paginated reads and the pluggable external-anchor mechanism
7. Integrate Clerk with FastAPI and implement local role enforcement (employee CRUD, auth middleware, API guards)
8. Build a minimal React frontend
9. Build and run the attack-demo test suite (the six scenarios in Section 6, including the recompute-and-hide and forged-anchor cases)
10. Document findings and prepare the live demo, using the recommended report structure (Section 15)
11. Layer in extended features (Sections 5.7-5.13) **only after** steps 1-10 produce a fully working, demoable core system. If time runs short, cut in this order: PDF evidence rendering → parallel-verification benchmark → suspicious-activity persistence → time-travel UI → external-anchor cloud adapter. Never cut the course-critical schema, ORM CRUD, view, real stored procedure, trigger, transaction, backup/restore, RBAC, or deployment evidence

---

## 14. Out of Scope (Explicitly, to Keep Focus)

- Full HR system features (payroll processing, leave management, performance reviews)
- Anchoring to a public blockchain or paid timestamping service — the free `AnchorStore` adapter uses a protected local file for development and a separate private GitHub repository for the deployed demonstration
- Full checkpoint-based partial re-verification in the CLI beyond storing the trusted checkpoint state (i.e., the checkpoint records exist; wiring the verifier to *resume* from one rather than always walking the full chain is a nice-to-have, not required)
- Multi-organization/multi-tenant support
- Mobile application
- **Merkle trees** — a real, more sophisticated alternative to a linear hash chain (O(log n) single-record verification, the same structure used by Git, Bitcoin, and Certificate Transparency logs). Deliberately not adopted: switching the core chain structure this late is genuine redesign risk, and this project's threat model doesn't need per-record inclusion proofs the way those systems do — the checkpointed linear chain already gives fast, resumable verification at far lower complexity. Worth stating explicitly in the report as a considered-and-rejected alternative
- **Full automated tamper recovery** (auto-restore from backup, rebuild the chain, generate a recovery report) — real backup/recovery orchestration disproportionate to this project's timeline relative to its demo payoff; discussed conceptually as future work instead of built
- **A natural-language-style audit search parser** — the structured filter UI already in Section 5.6 delivers most of the same auditor usefulness for a fraction of the engineering effort
- **Multiple independent audit streams anchored into a master hash** — a legitimate enterprise pattern, but this project's single Employee Records demo domain doesn't have a second genuinely distinct stream to split into

These are noted as potential future work but are deliberately excluded so the project's depth stays on the audit-trail integrity engine itself — the actual point of the project — rather than breadth of HR features.

---

## 15. Recommended Final Report & Viva Structure

To keep the database work visible as the primary deliverable rather than implied background work, the final report and viva presentation should follow this order:

1. **ER model + mapping** — `employees`, `roles`, `salary_history`, `audit_log`, `chain_state`, and the anchor mechanism
2. **Normalization** — the naive "before" schema, the anomalies it has, and why the final schema is in 3NF/BCNF
3. **Transactions + concurrency** — demonstrate that a data change and its audit entry commit atomically, and that concurrent writes are correctly serialized via `FOR UPDATE` locking
4. **Indexing + query optimization** — the B-tree indexes in use, and why keyset-paginated verification stays fast as the log grows
5. **Recovery + tamper evidence** — the live attack demo: single-entry tampering caught by the chain, and the recompute-and-hide case caught by anchoring

This structure mirrors the Curriculum Mapping Matrix (Section 11) and ensures every syllabus module the project touches is explicitly, visibly demonstrated rather than left for the grader to infer from the code.

---

## 16. Research Contribution & Evaluation Plan (Conference-Level Positioning)

Everything in Sections 1-15 makes Argus a strong *course* project. This section is what's additionally needed to make it a defensible *research* contribution — and, honestly, most of it is writing and measurement, not new features. Section 5.13 (hybrid verification) is the one genuine exception.

### 16.1 Contribution Statement

*"PostgreSQL, the most widely used open-source relational database, has no native mechanism for tamper-evident audit logging — a gap sharpened by AWS's 2025 discontinuation of QLDB. We present a lightweight, Postgres-native design combining hash-chained logging, row-level concurrency control, and signed external anchoring. We identify and formalize the 'recompute-and-hide' attack against naive hash-chaining schemes (as used by tools like pgMemento), show signed anchoring defeats it, and propose a checkpoint-parallelized verification strategy that improves verification wall-clock time over a naive sequential walk."*

**Deliberately split into two contributions, not one, so the paper's fate doesn't rest on a single number:**
1. **Security contribution (unconditional):** the recompute-and-hide attack formalization and its signed-anchor defeat. This holds regardless of what any benchmark shows — it's a cryptographic argument, not a performance measurement.
2. **Systems contribution (contingent on Section 16.8):** the parallel-checkpoint-verification hypothesis (Section 5.13). If the benchmark shows strong speedup, this is the headline result. If it shows a modest or negligible speedup, the paper still stands on (1) — with the performance finding honestly reported as "overhead stays low enough that the security gain is essentially free," which is itself a legitimate, publishable claim, just a less flashy one.

A cheap, fast pilot (a few thousand synthetic rows, 2-4 workers) run early — before investing in the full evaluation harness or the paper's framing — is worth doing specifically to learn which of these two stories the data actually supports, rather than discovering it only after Section 16.8 is fully built.

### 16.2 Threat Model

Formal adversary description: the attacker has database superuser privileges (arbitrary read/write on any table, can restart services) but **does not** have access to the external anchor location or the private signing key. Compromising the anchor-holding machine itself is explicitly out of scope — stated as a limitation (Section 16.6), not glossed over.

| Attack | Naive Audit Log (e.g., pgMemento-style) | Argus |
|---|---|---|
| `DELETE` a log row | Not detected | Detected (chain break) |
| `UPDATE` a log row | Not detected | Detected (chain break) |
| Edit + recompute all subsequent hashes | Not detected | Detected (anchor mismatch) |
| Plant a fake anchor entry | N/A (no anchor exists) | Rejected (invalid signature) |
| Privilege escalation to bypass logging | Possible if permissions misconfigured | Blocked (`REVOKE` at the role level, independent of app code) |

### 16.3 Security Analysis (Confidentiality, Integrity, Availability)

- **Confidentiality:** sensitive columns (salary, national ID/contact info) encrypted at rest via `pgcrypto`; the Compliance Auditor role can read audit metadata but never raw employee PII (Section 4)
- **Integrity:** the hash chain, business-rule constraints (Section 5.7), and signed anchoring (Section 5.10) together — this is the project's primary focus and where most of Sections 1-15 already contribute
- **Availability:** the verifier is stateless and read-only, so a crash mid-run requires only a restart, with no risk to the chain itself; if the anchor location is temporarily unreachable, ordinary logging continues uninterrupted, but detection of the recompute-and-hide attack (Section 6, scenario 5) is degraded until anchor connectivity resumes — a bounded, explicitly stated degradation, not a silent failure

### 16.4 Formal Algorithm

```
Algorithm 1: Audit Record Generation
Input:  old_row, new_row, actor, action, table_name
Output: audit_entry

1. prev_hash, seq ← SELECT tail_hash, sequence_id FROM chain_state FOR UPDATE
2. payload ← Serialize(actor, action, table_name, old_row, new_row, timestamp, prev_hash)
3. entry_hash ← SHA256(payload)
4. INSERT INTO audit_log VALUES (seq + 1, payload, entry_hash)
5. UPDATE chain_state SET tail_hash = entry_hash, sequence_id = seq + 1
6. COMMIT  -- same transaction as the triggering data change
```

### 16.5 Complexity Analysis

- **Insertion:** the marginal overhead hash-chaining adds is **O(1)** per write (one fixed-size hash computation, one singleton-row lock acquisition) — independent of table size *n*. This is separate from the standard **O(log n)** B-tree index-maintenance cost every indexed table already pays regardless of the audit mechanism; the two shouldn't be conflated
- **Full-chain verification:** O(n)
- **Checkpoint-resumed verification:** O(k), where k = entries since the last checkpoint
- **Parallel checkpoint verification (Section 5.13):** approximately O(n/P) wall-clock when the number of checkpoint segments c ≥ available workers P; bounded by O(n/c) — the largest single segment — when c < P
- **Time-travel reconstruction:** O(log n + m) given the composite index (Section 5.2), where m = number of historical entries applied to reconstruct the record; degrades to O(n) without that index

### 16.6 Failure Analysis

- **Power failure / partial writes:** the audit-log write and the triggering data change commit in the same transaction, so Postgres's own WAL-based crash recovery guarantees atomicity between them "for free" — a direct benefit of the same-transaction design decision (Section 8)
- **Transaction rollback:** if a business rule rejects an action, no successful-change entry is written. Optional failed-attempt telemetry is recorded separately by the API and is explicitly outside the atomic audit-chain guarantee
- **Verifier crash:** safe to restart; the dashboard correctly shows "not yet verified since [time]" rather than a false "clean" state until the next run completes
- **Concurrent writes:** handled by `FOR UPDATE` locking (Section 5.4); already covered by the attack demo
- **Anchor unreachable or corrupted:** logging continues; only recompute-and-hide detection is degraded until resolved — an explicit, bounded limitation, not a silent one

### 16.7 Comparison Matrix

| Feature | pgAudit | pgMemento | SQL Server Ledger | Argus |
|---|---|---|---|---|
| Tamper detection | No | No | Yes | Yes |
| Open source | Yes | Yes | No | Yes |
| PostgreSQL-native | Yes | Yes | No | Yes |
| External anchor | No | No | Partial | Yes |
| Digital signatures | No | No | No — hash/Merkle-digest based, not signature-based (verified against Microsoft Learn docs) | Yes |
| Independent verifier | No | No | Partial (in-engine stored procedure) | Yes (standalone, external process) |

*Note: the SQL Server Ledger cells were fact-checked against current Microsoft Learn documentation — it uses SHA-256 hashing organized into a Merkle tree to produce "database digests," exportable to external immutable storage (Azure Blob, Confidential Ledger, WORM). This is meaningfully different from an asymmetric digital signature, which proves authorship, not just integrity. A related system, Microsoft's Confidential Consortium Framework (used in Azure Confidential Ledger), does periodically sign its Merkle root as a distinct "signature transaction" — a closer precedent for Argus's own approach (Section 5.10) than SQL Server Ledger itself.*

### 16.8 Performance & Scalability Evaluation Plan

This is the part that requires real new engineering — a benchmark harness, not just documentation:

- **Core commitment:** measure insert/update/delete latency, audit-logging overhead, verification time, and storage overhead at 100 / 1,000 / 10,000 / 100,000 rows, comparing plain PostgreSQL against PostgreSQL+Argus
- **Stretch ceiling:** extending to 1,000,000 rows is good ambition but is its own deliverable (synthetic data generation, a proper benchmark harness, repeated runs for statistical validity) — commit to it only if the 100-100K results land with time to spare
- **Checkpoint interval as an independent variable:** the demo uses a fixed interval of 25 (Section 9), chosen for visibility in a small live demo — but a paper needs more than a magic number. Sweep the interval (e.g., 10 / 25 / 50 / 100 / 500) to empirically characterize the tradeoff between write-side overhead (more frequent signing) and verification speed (larger segments to walk per resumed check). This is a cheap addition given the harness already exists for the core evaluation — the same runs, reparameterized, not new infrastructure. Adaptive interval selection (Section 5.13) can remain a conceptual discussion unless time allows a simple heuristic to be tested against these swept fixed intervals
- Present as growth curves, not single numbers — a graph showing checkpointed verification staying near-flat while naive full-chain verification grows linearly is a stronger and more publishable result than any single measurement

### 16.9 Paper Content vs. Project Content

The dashboard (Section 5.6) stays fully in scope for the *project* — it's what your course grade and live demo depend on. It should **not**, however, dominate the *paper* — a written submission should foreground the threat model, algorithm, complexity analysis, and evaluation graphs above, with architecture/sequence diagrams standing in for what the dashboard shows visually in person.

### 16.10 Sequencing Note

Most of Sections 16.1-16.7 are writing/analysis that can happen alongside the existing 8-week build at near-zero additional engineering cost. Section 16.8 (the actual benchmark harness) is real additional work and should be budgeted as its own phase after the core system (Section 13, steps 1-10) is working — a paper's evaluation section can't be written before the numbers exist to report. A full academic paper draft is a natural next step once that data is in hand; recommend involving your DBMS professor as a mentor or co-author given the added rigor and legitimacy this stage benefits from.
