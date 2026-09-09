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
- `POST /api/auth/sync`: Syncs a newly authenticated Clerk user with the Argus PostgreSQL database. Must be called immediately after login.

### 2. Employee Management (HR Admin)
- `GET /api/employees`: List employees with pagination and search.
- `POST /api/employees`: Onboard a new employee.
- `PUT /api/employees/{id}`: Update an existing employee.
- `POST /api/employees/{id}/deactivate`: Soft-delete an employee.
- `POST /api/employees/{id}/salary`: Append a new salary record (history).

### 3. Audit & Compliance (Compliance Auditor)
- `GET /api/audit-logs`: Query tamper-evident audit logs with pagination and filters.
- `GET /api/audit-logs/export`: Download a digitally signed JSON artifact containing the full evidence chain.
- `POST /api/verify`: Trigger the `verifier` process to cryptographically validate the integrity of the database against the anchor.
- `GET /api/suspicious-activity`: Retrieve anomalous database behaviors identified by PostgreSQL triggers.
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
