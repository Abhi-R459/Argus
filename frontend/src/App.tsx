import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { SignedIn, SignedOut, SignIn } from '@clerk/clerk-react';
import { QueryClientProvider } from '@tanstack/react-query';
import { queryClient } from './lib/queryClient';
import HRAdminLayout from './layouts/HRAdminLayout';
import AuditorLayout from './layouts/AuditorLayout';
import RoleGuard from './components/auth/RoleGuard';
import AuthDispatcher from './components/auth/AuthDispatcher';
import { ErrorBoundary } from './components/common/ErrorBoundary';
import Dashboard from './pages/hr/Dashboard';
import EmployeeList from './pages/hr/EmployeeList';
import HRSettings from './pages/hr/HRSettings';
import AuditorOverview from './pages/auditor/AuditorOverview';
import AuditLogPage from './pages/auditor/AuditLogPage';
import ActivityPage from './pages/auditor/ActivityPage';
import AnalyticsPage from './pages/auditor/AnalyticsPage';
import TimeTravelPage from './pages/auditor/TimeTravelPage';
import AuditChainPage from './pages/auditor/AuditChainPage';
import CounterfactualPage from './pages/auditor/CounterfactualPage';
import ForensicEvidencePage from './pages/auditor/ForensicEvidencePage';

function ProtectedPortal({ allowedRole, children }: { allowedRole: 'hr_admin' | 'compliance_auditor'; children: React.ReactNode }) {
  if (import.meta.env.DEV && typeof window !== 'undefined' && (window as any).__E2E_ROLE__) {
    return <RoleGuard allowedRole={allowedRole}>{children}</RoleGuard>;
  }
  return (
    <SignedIn>
      <RoleGuard allowedRole={allowedRole}>{children}</RoleGuard>
    </SignedIn>
  );
}

function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <ErrorBoundary fallbackTitle="Application Error" fallbackSubtitle="An unexpected system error occurred. Please refresh or try again.">
          <Routes>
            {/* Root: redirect signed-in users based on role; show sign-in for guests */}
            <Route path="/" element={
              <>
                <SignedIn>
                  <AuthDispatcher />
                </SignedIn>
                <SignedOut>
                  <div className="min-h-screen bg-linear-canvas flex flex-col items-center justify-center p-4">
                    <div className="mb-8 text-center">
                      <h1 className="text-3xl font-bold text-linear-ink tracking-tight">Argus Audit Engine</h1>
                      <p className="text-linear-ink-subtle mt-2">Sign in to access your dashboard</p>
                    </div>
                    <SignIn routing="hash" />
                  </div>
                </SignedOut>
              </>
            } />

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
          </Routes>
        </ErrorBoundary>
      </BrowserRouter>
    </QueryClientProvider>
  );
}

export default App;
