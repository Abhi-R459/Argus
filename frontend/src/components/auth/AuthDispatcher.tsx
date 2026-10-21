import { Navigate } from 'react-router-dom';
import { useAuth } from './AuthProvider';
import ProfileLoadError from './ProfileLoadError';

export default function AuthDispatcher() {
  const { isLoaded, selectedRole, profileLoading, profileError, reloadProfile } = useAuth();

  if (!isLoaded || profileLoading) {
    return (
      <div className="min-h-screen bg-linear-canvas flex flex-col items-center justify-center p-4 text-linear-ink">
        <div className="w-10 h-10 border-4 border-linear-primary/20 border-t-linear-primary rounded-full animate-spin mb-4" />
        <p className="text-sm font-medium tracking-wide">Resolving portal credentials...</p>
      </div>
    );
  }

  if (profileError) {
    return <ProfileLoadError onRetry={reloadProfile} />;
  }

  if (selectedRole === 'compliance_auditor') {
    return <Navigate to="/auditor/overview" replace />;
  }

  return selectedRole === 'hr_admin' ? <Navigate to="/hr/dashboard" replace /> : <Navigate to="/" replace />;
}
