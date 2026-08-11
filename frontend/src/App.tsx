import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { SignedIn, SignedOut, SignIn } from '@clerk/clerk-react';
import { QueryClientProvider } from '@tanstack/react-query';
import { queryClient } from './lib/queryClient';
import HRAdminLayout from './layouts/HRAdminLayout';
import AuditorLayout from './layouts/AuditorLayout';
import Dashboard from './pages/hr/Dashboard';
import EmployeeList from './pages/hr/EmployeeList';
import AuditorOverview from './pages/auditor/AuditorOverview';
import AuditLogPage from './pages/auditor/AuditLogPage';
import ActivityPage from './pages/auditor/ActivityPage';
import AnalyticsPage from './pages/auditor/AnalyticsPage';

function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <Routes>
          {/* Root: redirect signed-in users; show sign-in for guests */}
          <Route path="/" element={
            <>
              <SignedIn>
                <Navigate to="/hr/dashboard" replace />
              </SignedIn>
              <SignedOut>
                <div className="min-h-screen bg-slate-950 flex flex-col items-center justify-center p-4">
                  <div className="mb-8 text-center">
                    <h1 className="text-3xl font-bold text-white tracking-tight">Argus Audit Engine</h1>
                    <p className="text-slate-400 mt-2">Sign in to access your dashboard</p>
                  </div>
                  <SignIn routing="hash" />
                </div>
              </SignedOut>
            </>
          } />

          {/* HR Admin routes */}
          <Route path="/hr" element={
            <SignedIn>
              <HRAdminLayout />
            </SignedIn>
          }>
            <Route path="dashboard" element={<Dashboard />} />
            <Route path="employees" element={<EmployeeList />} />
            <Route path="audits" element={<div className="p-4 animate-in fade-in text-slate-700">Audit Logs Coming Soon</div>} />
            <Route path="settings" element={<div className="p-4 animate-in fade-in text-slate-700">Settings Coming Soon</div>} />
          </Route>

          {/* Compliance Auditor routes */}
          <Route path="/auditor" element={
            <SignedIn>
              <AuditorLayout />
            </SignedIn>
          }>
            <Route index element={<Navigate to="overview" replace />} />
            <Route path="overview" element={<AuditorOverview />} />
            <Route path="chain" element={
              <div className="p-6 text-slate-500 text-sm animate-in fade-in">
                Chain view — same as Overview chain visualization (full page coming Week 7)
              </div>
            } />
            <Route path="log" element={<AuditLogPage />} />
            <Route path="activity" element={<ActivityPage />} />
            <Route path="analytics" element={<AnalyticsPage />} />
          </Route>
        </Routes>
      </BrowserRouter>
    </QueryClientProvider>
  );
}

export default App;
