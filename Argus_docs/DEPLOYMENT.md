# Deployment & Administration Guide

Argus is designed as a split-stack architecture consisting of a **React 19 SPA** (frontend) and a **FastAPI** service (backend), connected to a **PostgreSQL** database containing our tamper-evident triggers.

## 1. Backend Deployment (Render)

The FastAPI application is configured for deployment on [Render](https://render.com/) via Docker. The infrastructure-as-code configuration is available in [`render.yaml`](../render.yaml).

### Steps
1. Connect your GitHub repository to Render.
2. Select **Blueprint** to deploy using `render.yaml`.
3. The Blueprint will automatically provision:
   - A Docker-based Web Service (`argus-backend`) built from `api/Dockerfile`.
   - A Persistent Disk (`argus-anchor-data` mounted at `/data/anchor`) to store the cryptographic chain anchor file reliably.
4. Go to the Render Dashboard and populate the un-synced environment variables in the **Environment** tab:
   - `DATABASE_URL_MIGRATIONS`
   - `DATABASE_URL_HR_ADMIN`
   - `DATABASE_URL_COMPLIANCE_AUDITOR`
   - `VITE_CLERK_PUBLISHABLE_KEY`
   - `CLERK_SECRET_KEY`
   - `CLERK_JWT_KEY`
   - `CLERK_WEBHOOK_SIGNING_SECRET`
5. Navigate to the **Secret Files** section on Render and upload your `verifier_private_key.pem`. This is mounted to `/etc/secrets/verifier_private_key.pem`.

### Database Initialization
Before starting the API, the PostgreSQL database must be fully initialized.
Run the database migrations and table setup (which creates the necessary database schemas, roles, and cryptographic triggers) using the `db/` directory scripts (managed in Phase 1 & 6 by the DB team).
Ensure the `argus_migrations`, `argus_hr_admin`, and `argus_compliance_auditor` roles have been properly mapped.

## 2. Frontend Deployment (Vercel)

The React SPA is configured for deployment on [Vercel](https://vercel.com/) and includes routing configurations in [`frontend/vercel.json`](../frontend/vercel.json).

### Steps
1. Connect your GitHub repository to Vercel.
2. Set the Framework Preset to **Vite**.
3. Set the Root Directory to `frontend`.
4. The Build Command is `npm run build` and the Output Directory is `dist`.
5. Add the following Environment Variables in the Vercel dashboard:
   - `VITE_API_URL`: The public URL of your Render backend (e.g., `https://argus-backend.onrender.com`).
   - `VITE_CLERK_PUBLISHABLE_KEY`: Your Clerk Publishable Key.
6. Deploy. Vercel will automatically apply the `vercel.json` rewrites, routing all requests to `index.html` to support client-side routing, and apply necessary security headers.

## 3. User Administration (Clerk)

Argus delegates authentication and session management to **Clerk**.
1. Log in to the Clerk Dashboard.
2. Ensure your JWT template includes the `role` attribute in the token payload.
3. To grant permissions, navigate to the **Users** tab in Clerk and assign `hr_admin` or `compliance_auditor` roles via custom metadata.
4. When a user logs into Argus for the first time, a Clerk Webhook triggers the `/api/auth/sync` endpoint on the backend to synchronize the user profile to the local `users` PostgreSQL table. Ensure you configure this webhook inside the Clerk dashboard, pointing it to `https://argus-backend.onrender.com/api/auth/sync`, and inject the resulting Webhook Signing Secret into the Render environment variables.
