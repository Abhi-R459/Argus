# Argus Frontend Architecture

The Argus frontend is a Single-Page Application (SPA) built with React 19, TypeScript, and Vite. It is strictly typed and leverages TailwindCSS for styling. State and data fetching are handled by React Query (TanStack Query) combined with standard React Hooks.

## Directory Structure

```text
frontend/src/
├── components/       # Reusable UI building blocks
│   ├── auditor/      # Components specific to the Compliance Auditor dashboard
│   └── forms/        # Form components (Employee creation, edit, salary)
├── layouts/          # Top-level shell components (navigation, layout wrappers)
├── pages/            # Routable page views
│   ├── auditor/      # Pages for the Auditor dashboard
│   └── hr/           # Pages for the HR Admin dashboard
├── lib/              # Core utilities (API client setup, Clerk JWT injection)
├── services/         # Data fetching services (React Query queries/mutations)
└── types/            # TypeScript interfaces and Zod schemas
```

## Key Technologies
- **React 19 & Vite**: Fast development and building.
- **Clerk Auth**: Handles user sessions. The `@clerk/clerk-react` hooks are used heavily (e.g. `useAuth()`) to extract JWTs and pass them to our data-fetching services.
- **TanStack Query (React Query)**: Handles all server state, caching, pagination, and invalidation for our REST API endpoints.
- **TailwindCSS**: Utility-first CSS for all styling.
- **Lucide React**: Icon library.

## Dashboards (Role-Based Views)

Argus utilizes two distinct dashboards based on the logged-in user's role. Routing is strictly enforced via `<ProtectedRoute>` wrappers that check both authentication and RBAC roles.

### 1. HR Admin Dashboard
Located under `src/layouts/HRAdminLayout.tsx` and `src/pages/hr/`.
- **Purpose**: Provides full CRUD capabilities over the `employees` table, including adding salary history.
- **Key Components**:
  - `EmployeeList.tsx`: Page containing the paginated employee directory.
  - `EmployeeTable.tsx`: Displays the employee grid.
  - `forms/EmployeeForm.tsx` & `EmployeeEditForm.tsx`: Zod-validated react-hook-form implementations for onboarding/modifying personnel.

### 2. Compliance Auditor Dashboard
Located under `src/layouts/AuditorLayout.tsx` and `src/pages/auditor/`.
- **Purpose**: A tamper-evident analysis suite. It surfaces the cryptographic verification tools, the immutable audit trail, and anomalous behavior alerts.
- **Key Components**:
  - `VerificationControl.tsx`: Triggers the cryptographic chain verification and surfaces the success/failure state of the anchor check.
  - `AuditLogTable.tsx`: A paginated, filterable grid of all database events (INSERTS, UPDATES, DELETES) captured by the PostgreSQL triggers.
  - `DiffViewer.tsx`: A visual component that compares the `old_value` and `new_value` JSONB payloads from an audit log entry.
  - `ExportControl.tsx`: A secure download trigger that streams the cryptographically signed `evidence.json` directly from the backend.
  - `RiskPanel.tsx` & `ConcurrencyLab.tsx`: Real-time surfacing of suspicious activity flags and tools to test/monitor concurrent transactions.
  - `TimeTravelView.tsx`: A specialized view enabling the auditor to reconstruct the exact state of an employee record at any historical timestamp.

## Authentication Flow & API Integration
1. The user logs in via Clerk components.
2. React components use `const { getToken } = useAuth()` to retrieve a short-lived JWT.
3. This token is passed to service functions in `src/services/` (e.g. `auditService.ts`, `employeeService.ts`).
4. Service functions use a custom `fetchWithAuth` utility (in `src/lib/api.ts`) to inject the `Authorization: Bearer <token>` header and handle standard error responses (401, 403).
