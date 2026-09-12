import { Navigate, Outlet } from 'react-router-dom';
import { useAuth } from '@clerk/clerk-react';
import { useQuery } from '@tanstack/react-query';
import { fetchMyProfile, UserProfile } from '../../services/auditService';

interface RoleGuardProps {
  allowedRole: 'hr_admin' | 'compliance_auditor';
  children?: React.ReactNode;
}

export default function RoleGuard({ allowedRole, children }: RoleGuardProps) {
  const { getToken, isLoaded } = useAuth();

  const { data: profile, isLoading, isError } = useQuery<UserProfile>({
    queryKey: ['myProfile'],
    queryFn: () => fetchMyProfile(() => getToken()),
    enabled: isLoaded,
    staleTime: 60000,
  });

  if (!isLoaded || isLoading) {
    return (
      <div className="min-h-screen bg-slate-950 flex flex-col items-center justify-center p-4 text-slate-300">
        <div className="w-10 h-10 border-4 border-indigo-500/30 border-t-indigo-500 rounded-full animate-spin mb-4" />
        <p className="text-sm font-medium tracking-wide">Verifying role permissions...</p>
      </div>
    );
  }

  if (isError || !profile) {
    // If profile cannot be loaded, fallback to root
    return <Navigate to="/" replace />;
  }

  // If user role does not match the allowed role, redirect to their authorized portal
  if (profile.role !== allowedRole) {
    if (profile.role === 'compliance_auditor') {
      return <Navigate to="/auditor/overview" replace />;
    } else {
      return <Navigate to="/hr/dashboard" replace />;
    }
  }

  return children ? <>{children}</> : <Outlet />;
}
