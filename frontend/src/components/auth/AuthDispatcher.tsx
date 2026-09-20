import { Navigate } from 'react-router-dom';
import { useAuth } from '@clerk/clerk-react';
import { useQuery } from '@tanstack/react-query';
import { fetchMyProfile, UserProfile } from '../../services/auditService';

export default function AuthDispatcher() {
  const { getToken, isLoaded } = useAuth();

  const { data: profile, isLoading, isError } = useQuery<UserProfile>({
    queryKey: ['myProfile'],
    queryFn: () => fetchMyProfile(() => getToken()),
    enabled: isLoaded,
    staleTime: 60000,
    refetchInterval: false,
  });

  if (!isLoaded || isLoading) {
    return (
      <div className="min-h-screen bg-linear-canvas flex flex-col items-center justify-center p-4 text-linear-ink">
        <div className="w-10 h-10 border-4 border-linear-primary/20 border-t-linear-primary rounded-full animate-spin mb-4" />
        <p className="text-sm font-medium tracking-wide">Resolving portal credentials...</p>
      </div>
    );
  }

  if (isError || !profile) {
    // Default fallback to HR dashboard if error
    return <Navigate to="/hr/dashboard" replace />;
  }

  if (profile.role === 'compliance_auditor') {
    return <Navigate to="/auditor/overview" replace />;
  }

  return <Navigate to="/hr/dashboard" replace />;
}
