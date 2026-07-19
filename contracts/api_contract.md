# API Contract - Frozen after Week 1

This document specifies the endpoints, request/response models, and error responses agreed upon for the Argus application. The backend (FastAPI) and frontend (React) must conform to this contract to allow parallel, independent development.

## Base URL
All API paths are prefixed with `/api`.

---

## 1. Authentication & Session Context
Argus uses Clerk for authentication. The client must include the Clerk session JWT in the `Authorization` header on all request paths (except `/api/health`):
`Authorization: Bearer <clerk_token>`

### User Verification & Role Mapping (`POST /api/auth/sync`)
Synchronizes the authenticated Clerk user with the local `users` table and establishes the session context.
* **Request Header:** `Authorization: Bearer <clerk_token>`
* **Response (200 OK):**
  ```json
  {
    "user_id": 4,
    "clerk_user_id": "user_2T...",
    "full_name": "Jane Doe",
    "email": "jane.doe@company.com",
    "role": "hr_admin",
    "is_active": true
  }
  ```

---

## 2. Employee Directory & CRUD

### List Employees (`GET /api/employees`)
Retrieves the employee directory. Backed by `v_employee_directory`.
* **Query Parameters:**
  * `search` (string, optional): Filters by name or email.
  * `page` (int, default=1)
  * `limit` (int, default=20)
* **Response (200 OK):**
  ```json
  {
    "items": [
      {
        "employee_id": 12,
        "full_name": "Alice Smith",
        "email": "alice.smith@company.com",
        "role_title": "Software Engineer",
        "department_name": "Engineering",
        "salary": 95000.00,
        "date_hired": "2024-03-15",
        "is_active": true
      }
    ],
    "total": 1,
    "page": 1,
    "pages": 1
  }
  ```

### Create Employee (`POST /api/employees`)
Creates a new employee record.
* **Role Restricton:** `hr_admin` only.
* **Request Body:**
  ```json
  {
    "full_name": "Bob Johnson",
    "email": "bob.johnson@company.com",
    "role_id": 2,
    "national_id": "NID-999-12-3456",
    "contact_info": "123 Main St, New York, NY",
    "date_hired": "2026-07-20",
    "salary": 80000.00
  }
  ```
* **Response (201 Created):**
  ```json
  {
    "employee_id": 13,
    "full_name": "Bob Johnson",
    "email": "bob.johnson@company.com",
    "role_id": 2,
    "date_hired": "2026-07-20",
    "is_active": true
  }
  ```

### Update Employee (`PATCH /api/employees/{id}`)
Modifies an existing employee record.
* **Role Restriction:** `hr_admin` only.
* **Request Body:**
  ```json
  {
    "full_name": "Bob Johnson",
    "role_id": 3,
    "contact_info": "456 Oak St, Brooklyn, NY"
  }
  ```
* **Response (200 OK):**
  ```json
  {
    "employee_id": 13,
    "full_name": "Bob Johnson",
    "email": "bob.johnson@company.com",
    "role_id": 3,
    "is_active": true
  }
  ```

### Deactivate Employee (`DELETE /api/employees/{id}`)
Soft-deletes an employee record (sets `is_active = false`).
* **Role Restriction:** `hr_admin` only.
* **Response (200 OK):**
  ```json
  {
    "employee_id": 13,
    "is_active": false
  }
  ```

---

## 3. Salaries & Salary History

### Add Salary Record (`POST /api/employees/{id}/salary`)
Adds a new salary amount and effective date.
* **Role Restriction:** `hr_admin` only. (Trigger check: cannot decrease pay by >30% or edit own salary).
* **Request Body:**
  ```json
  {
    "amount": 110000.00,
    "effective_date": "2026-08-01"
  }
  ```
* **Response (201 Created):**
  ```json
  {
    "salary_history_id": 42,
    "employee_id": 13,
    "amount": 110000.00,
    "effective_date": "2026-08-01"
  }
  ```

---

## 4. Audit Log & Verification

### Retrieve Audit Logs (`GET /api/audit-logs`)
Retrieves the paginated audit logs. Visible only to `compliance_auditor`.
* **Query Parameters:**
  * `actor_id` (int, optional)
  * `action` (string, optional: `INSERT` / `UPDATE` / `DELETE`)
  * `table_name` (string, optional)
  * `severity` (string, optional: `INFO` / `WARNING` / `CRITICAL`)
  * `page` (int, default=1)
  * `limit` (int, default=20)
* **Response (200 OK):**
  ```json
  {
    "items": [
      {
        "sequence_id": 125,
        "actor_name": "Jane Doe",
        "employee_id": 13,
        "action": "UPDATE",
        "table_name": "employees",
        "row_id": 13,
        "old_value": { "role_id": 2 },
        "new_value": { "role_id": 3 },
        "severity": "INFO",
        "entry_hash": "f683a7...",
        "previous_hash": "d4c92b...",
        "created_at": "2026-07-19T10:00:00Z"
      }
    ],
    "total": 125,
    "page": 1,
    "pages": 7
  }
  ```

### Run Verification (`POST /api/verify`)
Triggers the standalone verifier to scan the hash chain.
* **Role Restriction:** `compliance_auditor` only.
* **Response (200 OK):**
  * **Intact:**
    ```json
    {
      "status": "intact",
      "entries_scanned": 150,
      "anchor_match": true,
      "last_verified_sequence_id": 150,
      "tampered_sequence_id": null,
      "details": "Chain walks successfully. Tail hash matches external anchor store."
    }
    ```
  * **Tampered Chain:**
    ```json
    {
      "status": "tampered",
      "entries_scanned": 150,
      "anchor_match": false,
      "last_verified_sequence_id": 89,
      "tampered_sequence_id": 90,
      "details": "Chain broke at sequence ID 90. Expected hash mismatch."
    }
    ```
  * **Recompute-and-Hide Detected:**
    ```json
    {
      "status": "tampered",
      "entries_scanned": 150,
      "anchor_match": false,
      "last_verified_sequence_id": 150,
      "tampered_sequence_id": null,
      "details": "Chain is internally self-consistent but tail hash does not match last anchored checkpoint."
    }
    ```

---

## 5. Time-Travel Queries

### Reconstruct State (`GET /api/employees/{id}/time-travel`)
Reconstructs an employee's record state at a specific past timestamp.
* **Role Restriction:** `compliance_auditor` only.
* **Query Parameters:**
  * `timestamp` (string, ISO-8601 required, e.g., `2026-07-15T12:00:00Z`)
* **Response (200 OK):**
  ```json
  {
    "employee_id": 13,
    "full_name": "Bob Johnson",
    "email": "bob.johnson@company.com",
    "role_title": "Junior Engineer",
    "department_name": "Engineering",
    "salary": 80000.00,
    "date_hired": "2026-07-20",
    "is_active": true,
    "as_of": "2026-07-15T12:00:00Z"
  }
  ```

---

## 6. Suspicious Activity Monitoring

### List Flags (`GET /api/suspicious-activity`)
Lists the persisted suspicious activity alerts.
* **Role Restriction:** `compliance_auditor` only.
* **Response (200 OK):**
  ```json
  [
    {
      "flag_id": 1,
      "audit_log_sequence_id": 104,
      "flag_reason": "High frequency: 5 changes made by Jane Doe in under 2 minutes",
      "reviewed_by": null,
      "reviewed_at": null,
      "created_at": "2026-07-19T09:12:00Z"
    }
  ]
  ```

### Review Flag (`POST /api/suspicious-activity/{id}/review`)
Marks a flag as reviewed.
* **Role Restriction:** `compliance_auditor` only.
* **Response (200 OK):**
  ```json
  {
    "flag_id": 1,
    "reviewed_by_user_id": 5,
    "reviewed_at": "2026-07-19T10:05:00Z"
  }
  ```

---

## 7. Error Responses
Standard RFC 7807 problem details or matching JSON error structures.

* **401 Unauthorized:**
  ```json
  { "detail": "Invalid or expired authorization token." }
  ```
* **403 Forbidden (RBAC):**
  ```json
  { "detail": "Privilege separation error: Auditor cannot perform HR CRUD." }
  ```
* **422 Unprocessable Entity (Validation):**
  ```json
  {
    "detail": [
      {
        "loc": ["body", "email"],
        "msg": "value is not a valid email address",
        "type": "value_error.email"
      }
    ]
  }
  ```
