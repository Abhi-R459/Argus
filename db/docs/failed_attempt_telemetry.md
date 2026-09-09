# API-Side Failed-Attempt Telemetry Contract (DB-016)

## Purpose

This document defines the contract between the **FastAPI application layer** (Nidhurshek's domain)
and the **database layer** (Abhinav's domain) for recording failed access attempts in the
`suspicious_activity_flags` table.

The `suspicious_activity_flags` table is populated through two distinct channels:

1. **Automatically** — by the `refresh_suspicious_activity_flags()` stored procedure (DB-019),
   which scans `audit_log` for patterns like repeated salary decreases or mass deletions.
2. **Manually** — by the API layer inserting flags for application-level failures that never
   reach the database (e.g., unauthorized endpoint hits, JWT validation failures).

---

## When the API Must Insert a Flag

The API is responsible for inserting a `suspicious_activity_flags` row in these scenarios:

| Scenario | Trigger Condition | Flag Reason String |
|----------|------------------|--------------------|
| Unauthorized endpoint access | HTTP 403 from Clerk RBAC middleware | `"unauthorized_access: <endpoint>"` |
| JWT verification failure | Clerk returns invalid/expired token | `"jwt_failure: <clerk_user_id>"` |
| Rate-limit exceeded | >10 requests / minute from same user | `"rate_limit_exceeded: <clerk_user_id>"` |
| Unexpected role escalation attempt | User tries to access admin-only resource | `"role_escalation_attempt: <clerk_user_id>"` |

---

## Database Insert Contract

When the API logs a failed attempt, it **must** follow this exact contract:

```sql
-- Prerequisites:
--   1. A valid audit_log row must exist (the flag is linked to a real audit event).
--   2. If no DB operation was attempted, use the most recent audit_log.sequence_id
--      for the affected employee as the anchor.
--   3. The actor_user_id must be resolvable to a row in users.user_id.
--      Use a dedicated system user (user_id = 0 / system) if no auth was established.

INSERT INTO suspicious_activity_flags (
    audit_log_sequence_id,   -- FK → audit_log.sequence_id (most recent event)
    reviewed_by_user_id,     -- NULL initially; set by auditor on review
    reviewed_at,             -- NULL initially
    flag_reason              -- Human-readable reason string (max 255 chars)
)
VALUES (
    :latest_sequence_id,
    NULL,
    NULL,
    :flag_reason_string
);
```

---

## Session Variable Requirements

Before any DML operation that touches `employees` or `salary_history`, the API **must** set:

```sql
-- Identifies the authenticated user for audit_log.actor_user_id
SET LOCAL argus.actor_user_id = <user_id>;   -- INT: users.user_id

-- Identifies the actor's employee_id (for self-modification block trigger DB-014)
SET LOCAL argus.actor_employee_id = <employee_id>;  -- INT: employees.employee_id (or 0 if not an employee)
```

These variables are LOCAL to the current transaction and are automatically cleared on COMMIT/ROLLBACK.

---

## Ownership Boundary

| Responsibility | Owner |
|---------------|-------|
| Insert `suspicious_activity_flags` for DB-detected anomalies (salary, deletions) | Abhinav (DB-019 procedure) |
| Insert `suspicious_activity_flags` for API-layer auth failures | Nidhurshek (FastAPI middleware) |
| Review and mark flags as reviewed | Compliance Auditor (application flow) |

---

## Table Reference

```sql
CREATE TABLE suspicious_activity_flags (
    flag_id                  SERIAL PRIMARY KEY,
    audit_log_sequence_id    BIGINT NOT NULL REFERENCES audit_log(sequence_id),
    reviewed_by_user_id      INT    REFERENCES users(user_id),
    reviewed_at              TIMESTAMPTZ,
    flag_reason              VARCHAR(255) NOT NULL,
    created_at               TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);
```
