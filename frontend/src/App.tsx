import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { SignedIn, SignedOut, SignIn } from '@clerk/clerk-react';
import { QueryClientProvider } from '@tanstack/react-query';
import { queryClient } from './lib/queryClient';
import HRAdminLayout from './layouts/HRAdminLayout';
import Dashboard from './pages/hr/Dashboard';
import EmployeeList from './pages/hr/EmployeeList';

function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <Routes>
          <Route path="/" element={
            <>
              <SignedIn>
                <Navigate to="/hr/dashboard" replace />
              </SignedIn>
              <SignedOut>
                <div className="min-h-screen bg-slate-50 flex flex-col items-center justify-center p-4">
                  <div className="mb-8 text-center">
                    <h1 className="text-3xl font-bold text-slate-900 tracking-tight">Argus Audit Engine</h1>
                    <p className="text-slate-500 mt-2">Sign in to access your dashboard</p>
                  </div>
                  <SignIn routing="hash" />
                </div>
              </SignedOut>
            </>
          } />
          
          <Route path="/hr" element={
            <SignedIn>
              <HRAdminLayout />
            </SignedIn>
          }>
            <Route path="dashboard" element={<Dashboard />} />
            <Route path="employees" element={<EmployeeList />} />
            <Route path="audits" element={<div className="p-4 animate-in fade-in">Audit Logs Coming Soon</div>} />
            <Route path="settings" element={<div className="p-4 animate-in fade-in">Settings Coming Soon</div>} />
          </Route>
        </Routes>
      </BrowserRouter>
    </QueryClientProvider>
  );
}

export default App;
