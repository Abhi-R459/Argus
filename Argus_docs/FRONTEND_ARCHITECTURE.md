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

## Dashboards & Dual-Theme Architecture

Argus utilizes two distinct dashboards based on the logged-in user's role, enforcing strict aesthetic and cognitive isolation:
- **HR Admin Dashboard (`src/layouts/HRAdminLayout.tsx`, `src/pages/hr/`):**
  - **Theme:** Clean, high-legibility enterprise light mode (`.hr-light` / Slate-50 canvas, crisp white cards, Slate-200 borders, distinct status pills).
  - **Purpose:** Full CRUD capabilities over workforce directory, employee profiles, and salary adjustments.
  - **Key Components:**
    - `EmployeeList.tsx`: Paginated employee directory with live search and department filtering.
    - `EmployeeTable.tsx`: Tabular view with inline status badges and keyboard selection.
    - `EmployeeSheet.tsx`: Slide-over lateral drawer for fast personnel inspection, compensation timelines, and PII status.
    - `forms/EmployeeForm.tsx` & `EmployeeEditForm.tsx`: Zod-validated react-hook-form modals for onboarding and updates.
- **Compliance Auditor Dashboard (`src/layouts/AuditorLayout.tsx`, `src/pages/auditor/`):**
  - **Theme:** Immersive Linear-inspired dark mode (`#0c0d0e` / Neutral 950 canvas, `#16181d` cards, hairline borders, monospace digests, glowing emerald/crimson integrity badges).
  - **Purpose:** Tamper-evident forensic analysis, cryptographic verification, and out-of-band audit trail exploration.
  - **Key Components:**
    - `AuditChainPage.tsx` & `ChainVisualization.tsx`: Dedicated full-page audit chain block visualizer with keyset pagination and sequence deep-linking.
    - `DetailSheet.tsx`: Origin-aware sliding block inspector drawer with field-level syntax-highlighted diffs (`DiffViewer.tsx`).
    - `VerificationControl.tsx` & `SecurityPosture.tsx`: On-demand cryptographic verifier trigger with live 0-100 SVG posture dial.
    - `AuditLogTable.tsx`: Forensic log explorer with keyset pagination, multi-filtering, and HMAC blind index search.
    - `TimeTravelView.tsx`: Zero-latency typeahead combobox with sub-second datetime precision (`HH:mm:ss`), quick presets, and chronological mutation timeline replay.
    - `ExportControl.tsx`: Secure exporter streaming signed evidence JSON and air-gapped `.arguspack` bundles.
    - `RiskPanel.tsx` & `ConcurrencyLab.tsx`: Real-time risk alert reviews and live 2PL multi-worker race testing.

## Motion Physics & Transition Engineering

Argus avoids jarring layout pop-ins or uncoordinated DOM destruction through dedicated physics hooks:
1. **Two-Way Lateral Drawers (`DetailSheet.tsx`, `EmployeeSheet.tsx`):**
   - Uses CSS lateral drawer classes (`.drawer-slide-right` ➔ `.drawer-slide-right-open`) with Apple/Linear 240ms deceleration curves (`cubic-bezier(0.16, 1, 0.3, 1)`).
   - Content and domain entities are cached across unmount cycles (`cachedContent`, `cachedEmployee`) to ensure zero visual flashing during dismissal.
2. **Two-Way Spring Modals (`useModalTransition`):**
   - Coordinates double `requestAnimationFrame` entries (`scale(0.95)`, `opacity: 0` ➔ `scale(1.0)`, `opacity: 1`) and delays unmounting until exit animations complete.
3. **Table Row Accordion Animation (`useAccordionTransition`):**
   - Animates table row expansions smoothly using CSS Grid fractional height tracks (`grid-template-rows: 0fr` ➔ `1fr`) with rotating 180° chevrons.

## Keyboard Ergonomics & Form Defense
- **Keyboard Navigation (`useKeyboardNav`):** `J` / `K` for table row selection, `Enter` to open side-sheets, `Escape` to close drawers/modals, and `/` to focus search bars.
- **Browser Autofill Suppression:** All search inputs enforce `autoComplete="off"`, `autoCorrect="off"`, `spellCheck={false}`, and password manager suppression attributes (`data-lpignore="true"`), preventing address/contact dropdowns over search inputs.

## Authentication Flow & API Integration
1. The user logs in via Clerk components.
2. React components use `const { getToken } = useAuth()` to retrieve a short-lived JWT.
3. This token is passed to service functions in `src/services/` (e.g. `auditService.ts`, `employeeService.ts`).
4. Service functions use a custom `fetchWithAuth` utility (in `src/lib/api.ts`) to inject the `Authorization: Bearer <token>` header and handle standard error responses (401, 403).
