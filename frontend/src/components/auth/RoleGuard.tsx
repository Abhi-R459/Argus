import { Navigate, Outlet } from 'react-router-dom';
import { useAuth } from './AuthProvider';
import ProfileLoadError from './ProfileLoadError';

interface RoleGuardProps {
  allowedRole: 'hr_admin' | 'compliance_auditor';
  children?: React.ReactNode;
}

export default function RoleGuard({ allowedRole, children }: RoleGuardProps) {
  const devE2ERole = import.meta.env.DEV && typeof window !== 'undefined' ? window.__E2E_ROLE__ : undefined;

  const { isLoaded, selectedRole, profileLoading, profileError, reloadProfile } = useAuth();

  if (devE2ERole) {
    if (devE2ERole !== allowedRole) {
      return <Navigate to={devE2ERole === 'compliance_auditor' ? '/auditor/overview' : '/hr/dashboard'} replace />;
    }
    return children ? <>{children}</> : <Outlet />;
  }

  if (!isLoaded || profileLoading) {
    return (
      <div className="min-h-screen bg-linear-canvas flex flex-col items-center justify-center p-4 text-linear-ink">
        <div className="w-10 h-10 border-4 border-linear-primary/20 border-t-linear-primary rounded-full animate-spin mb-4" />
        <p className="text-sm font-medium tracking-wide">Verifying role permissions...</p>
      </div>
    );
  }

  if (profileError) {
    return <ProfileLoadError onRetry={reloadProfile} />;
  }

  // If user role does not match the allowed role, redirect to their authorized portal
  if (selectedRole !== allowedRole) {
    if (selectedRole === 'compliance_auditor') {
      return <Navigate to="/auditor/overview" replace />;
    } else if (selectedRole === 'hr_admin') {
      return <Navigate to="/hr/dashboard" replace />;
    }
    return <Navigate to="/" replace />;
  }

  return children ? <>{children}</> : <Outlet />;
}
