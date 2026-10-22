import { lazy, Suspense, useMemo } from 'react';
import { BrowserRouter, Routes, Route, Navigate, Link } from 'react-router-dom';
import { useAuth } from './components/auth/AuthProvider';
import SignIn from './components/auth/SignIn';
import SignUp from './components/auth/SignUp';
import RoleChooser from './components/auth/RoleChooser';
import { QueryClientProvider } from '@tanstack/react-query';
import { createQueryClient } from './lib/queryClient';
import HRAdminLayout from './layouts/HRAdminLayout';
import AuditorLayout from './layouts/AuditorLayout';
import RoleGuard from './components/auth/RoleGuard';
import AuthDispatcher from './components/auth/AuthDispatcher';
import ProfileLoadError from './components/auth/ProfileLoadError';
import { ErrorBoundary } from './components/common/ErrorBoundary';
const Dashboard = lazy(() => import('./pages/hr/Dashboard'));
const EmployeeList = lazy(() => import('./pages/hr/EmployeeList'));
const HRSettings = lazy(() => import('./pages/hr/HRSettings'));
const UndoHistory = lazy(() => import('./pages/hr/UndoHistory'));
const AuditorOverview = lazy(() => import('./pages/auditor/AuditorOverview'));
const AuditLogPage = lazy(() => import('./pages/auditor/AuditLogPage'));
const ActivityPage = lazy(() => import('./pages/auditor/ActivityPage'));
const AnalyticsPage = lazy(() => import('./pages/auditor/AnalyticsPage'));
const TimeTravelPage = lazy(() => import('./pages/auditor/TimeTravelPage'));
const AuditChainPage = lazy(() => import('./pages/auditor/AuditChainPage'));
const CounterfactualPage = lazy(() => import('./pages/auditor/CounterfactualPage'));
const ForensicEvidencePage = lazy(() => import('./pages/auditor/ForensicEvidencePage'));

function ProtectedPortal({ allowedRole, children }: { allowedRole: 'hr_admin' | 'compliance_auditor'; children: React.ReactNode }) {
  const { isLoaded, isSignedIn } = useAuth();
  if (import.meta.env.DEV && typeof window !== 'undefined' && window.__E2E_ROLE__) {
    return <RoleGuard allowedRole={allowedRole}>{children}</RoleGuard>;
  }
  if (!isLoaded) return <div role="status">Loading your session…</div>;
  if (!isSignedIn) return <Navigate to="/" replace />;
  return <RoleGuard allowedRole={allowedRole}>{children}</RoleGuard>;
}

function App() {
  const { userId, isLoaded, isSignedIn, selectedRole, profileLoading, profileError, reloadProfile } = useAuth();
  const sessionKey = import.meta.env.DEV && window.__E2E_ROLE__ ? `e2e:${window.__E2E_ROLE__}` : userId ?? 'signed-out';
  // A new account gets a new cache; HR and audit data never cross sessions.
  const cacheKey = sessionKey + ':' + (selectedRole ?? 'none');
  const queryClient = useMemo(() => createQueryClient(), [cacheKey]);
  return (
    <QueryClientProvider key={cacheKey} client={queryClient}>
      <BrowserRouter>
        <ErrorBoundary fallbackTitle="Application Error" fallbackSubtitle="An unexpected system error occurred. Please refresh or try again.">
          <Suspense fallback={<div className="min-h-screen bg-linear-canvas text-linear-ink flex items-center justify-center" role="status">Loading page…</div>}>
          <Routes>
            {/* Root: redirect signed-in users based on role; show sign-in for guests */}
            <Route path="/" element={
              isSignedIn ? (profileLoading ? <div role="status">Loading your account…</div> : profileError ? <ProfileLoadError onRetry={reloadProfile} /> : selectedRole ? <AuthDispatcher /> : <RoleChooser />) : (
                <div className="min-h-screen bg-linear-canvas flex flex-col items-center justify-center p-4">
                  <div className="mb-8 text-center">
                    <h1 className="text-3xl font-bold text-linear-ink tracking-tight">Argus Audit Engine</h1>
                    <p className="text-linear-ink-subtle mt-2">Sign in or create an account to access your dashboard</p>
                  </div>
                  <Link to="/sign-up" className="mb-5 rounded-xl bg-linear-primary px-5 py-3 font-semibold text-white">Create an account</Link>
                  {isLoaded ? <SignIn /> : <div role="status">Loading sign-in…</div>}
                </div>
              )
            } />

            <Route path="/sign-up" element={isSignedIn ? <Navigate to="/" replace /> : <SignUp isLoaded={isLoaded} />} />

            <Route path="/auth/callback" element={isLoaded ? <Navigate to="/" replace /> : <div role="status">Completing sign-in…</div>} />
            {/* HR Admin routes */}
            <Route path="/hr" element={
              <ProtectedPortal allowedRole="hr_admin">
                <HRAdminLayout />
              </ProtectedPortal>
            }>
              <Route index element={<Navigate to="dashboard" replace />} />
              <Route path="dashboard" element={<Dashboard />} />
              <Route path="employees" element={<EmployeeList />} />
              <Route path="settings" element={<HRSettings />} />
              <Route path="history" element={<UndoHistory />} />
            </Route>

            {/* Compliance Auditor routes */}
            <Route path="/auditor" element={
              <ProtectedPortal allowedRole="compliance_auditor">
                <AuditorLayout />
              </ProtectedPortal>
            }>
              <Route index element={<Navigate to="overview" replace />} />
              <Route path="overview" element={<AuditorOverview />} />
              <Route path="chain" element={<AuditChainPage />} />
              <Route path="log" element={<AuditLogPage />} />
              <Route path="time-travel" element={<TimeTravelPage />} />
              <Route path="counterfactual" element={<CounterfactualPage />} />
              <Route path="forensic-evidence" element={<ForensicEvidencePage />} />
              <Route path="activity" element={<ActivityPage />} />
              <Route path="analytics" element={<AnalyticsPage />} />
            </Route>
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
          </Suspense>
        </ErrorBoundary>
      </BrowserRouter>
    </QueryClientProvider>
  );
}

export default App;
