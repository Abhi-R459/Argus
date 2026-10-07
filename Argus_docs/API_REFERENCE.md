# Argus API Reference

Argus provides a RESTful JSON API built with FastAPI. It enables dashboards to manage employees, query audit logs, and trigger cryptographic chain verifications.

## OpenAPI Specification
A complete machine-readable OpenAPI (Swagger) specification is available in this repository:
[`openapi.json`](./openapi.json)

When running the application locally, you can view the interactive documentation at:
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

## Authentication
All protected endpoints require a Bearer token in the `Authorization` header. Argus delegates authentication to **Clerk**.
The token must be a valid Clerk JWT.

```http
Authorization: Bearer <clerk_jwt_token>
```

### Roles and Authorization
Argus enforces strict Role-Based Access Control (RBAC):
- **HR Admin (`hr_admin`)**: Has access to employee directory and employee modification endpoints.
- **Compliance Auditor (`compliance_auditor`)**: Has read-only access to employee directory, and exclusive access to audit logs, cryptographic verification, and export tools.

## Key Endpoints

### 1. Health & Auth
- `GET /api/health`: Public endpoint to check system status.
- `GET /api/health/ready`: Readiness endpoint; checks that both least-privilege runtime database roles can connect. It does not verify audit-chain integrity.
- `POST /api/auth/sync`: Syncs a newly authenticated Clerk user with the Argus PostgreSQL database. Must be called immediately after login.

### 2. Employee Management & Workforce (HR Admin)
- `GET /api/employees`: List employees with pagination, search, and department filtering.
- `POST /api/employees`: Onboard a new employee (triggers database-level `pgcrypto` column encryption).
- `PUT /api/employees/{id}`: Update an existing employee profile.
- `POST /api/employees/{id}/deactivate`: Soft-delete an employee.
- `POST /api/employees/{id}/salary`: Append a new salary record (enforcing in-engine $>30\%$ drop blocks and self-modification blocks).
- `GET /api/dashboard/stats`: Retrieve workforce aggregate metrics, headcount, and department salary distributions.
- `POST /api/checkpoints/create`: HR-admin-only action that signs all audit events since the previous checkpoint, returns the checkpoint ID, sequence boundary, Merkle root, leaf count, sealed-entry count, signature status, and `external_anchor_created: false`, and records the requesting HR admin. Requires migration `023_hr_checkpoint_creation` and a configured development/demo signing key. It does not create an external anchor; production currently returns `503` until a managed signer is available. Returns `409` if there are no pending events or a concurrent checkpoint already sealed the current boundary.

### 3. Audit, Compliance & Forensics (Compliance Auditor)
- `GET /api/audit-logs`: Query tamper-evident audit logs with keyset pagination, action/table/severity filters, and server-side HMAC blind index lookups.
- `GET /api/audit-logs/chain`: Keyset-paginated live audit chain blocks for deep block inspection.
- `GET /api/audit-logs/export`: Download a digitally signed JSON artifact containing the full evidence chain.
- `GET /api/audit-logs/export-pack`: Stream portable, air-gapped `.arguspack` evidence zip archives embedding zero-dependency pure-Python RFC 8032 verifiers.
- `GET /api/audit-logs/time-travel/{id}`: Reconstruct historical employee state as of an exact microsecond timestamp via PostgreSQL stored function `reconstruct_employee_state()`.
- `GET /api/anchor/status`: Inspect configured anchor status and the distance between the latest checkpoint and current audit-chain tail. Local-file status is not evidence of an independent external trust domain.
- `GET /api/audit-logs/telemetry`: Query live PostgreSQL system telemetry (buffer cache hit ratios, relation sizes) and compute real-time security posture score (0–100).
- `POST /api/audit-logs/concurrency-race`: Trigger parallel concurrent write transactions to empirically demonstrate Two-Phase Locking (2PL) serialization without gaps.
- `POST /api/verify`: Trigger on-demand cryptographic chain verification against the external anchor store.
- `GET /api/suspicious-activity`: Retrieve anomalous database behaviors identified by in-engine triggers.
- `POST /api/suspicious-activity/{id}/review`: Mark a suspicious activity flag as reviewed by the auditor.

## Responses & Errors
Standard HTTP status codes are used:
- `200 OK` / `201 Created`: Success.
- `400 Bad Request`: Client-side input validation failure.
- `401 Unauthorized`: Missing or invalid Clerk JWT.
- `403 Forbidden`: Valid token, but the user's role lacks permissions (Privilege Separation).
- `404 Not Found`: Resource does not exist.
- `422 Unprocessable Entity`: Pydantic schema validation failure.
- `500 Internal Server Error`: Server-side processing failure.
