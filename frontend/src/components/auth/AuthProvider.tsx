import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react';
import { useAuth as useClerkAuth, useUser } from '@clerk/react';
import type { WorkspaceRole } from '../../lib/workspaceRole';
import { chooseAccountRole, fetchMyProfile } from '../../services/auditService';

interface AuthState {
  isLoaded: boolean;
  isSignedIn: boolean;
  userId: string | null;
  user: { fullName: string | null; email: string | null; id: string } | null;
  selectedRole: WorkspaceRole | null;
  profileLoading: boolean;
  profileError: string | null;
  reloadProfile: () => void;
  chooseRole: (role: WorkspaceRole) => Promise<void>;
  getToken: (options?: { skipCache?: boolean }) => Promise<string | null>;
  signOut: () => Promise<void>;
}

const AuthContext = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const clerkAuth = useClerkAuth();
  const { user } = useUser();
  const [selectedRole, setSelectedRole] = useState<WorkspaceRole | null>(null);
  const [profileLoading, setProfileLoading] = useState(true);
  const [profileError, setProfileError] = useState<string | null>(null);
  const [profileRevision, setProfileRevision] = useState(0);
  const userId = clerkAuth.userId ?? null;

  useEffect(() => {
    let active = true;
    setSelectedRole(null);
    setProfileError(null);
    if (!clerkAuth.isLoaded || !userId) {
      setProfileLoading(!clerkAuth.isLoaded);
      return () => { active = false; };
    }
    setProfileLoading(true);
    fetchMyProfile(() => clerkAuth.getToken())
      .then((profile) => { if (active) setSelectedRole(profile.role); })
      .catch((error: unknown) => { if (active) setProfileError(error instanceof Error ? error.message : 'Could not load account.'); })
      .finally(() => { if (active) setProfileLoading(false); });
    return () => { active = false; };
  }, [clerkAuth.isLoaded, clerkAuth.getToken, userId, profileRevision]);
  const getToken = useCallback(
    (options?: { skipCache?: boolean }) => clerkAuth.getToken({ skipCache: options?.skipCache }),
    [clerkAuth],
  );
  const reloadProfile = useCallback(() => setProfileRevision((revision) => revision + 1), []);
  const chooseRole = useCallback(async (role: WorkspaceRole) => {
    const profile = await chooseAccountRole(role, getToken);
    setSelectedRole(profile.role);
    setProfileError(null);
  }, [getToken]);
  const signOut = useCallback(async () => {
    setSelectedRole(null);
    await clerkAuth.signOut();
  }, [clerkAuth]);
  const value = useMemo(() => ({
    isLoaded: clerkAuth.isLoaded,
    isSignedIn: clerkAuth.isSignedIn ?? false,
    userId,
    user: user ? { fullName: user.fullName, email: user.primaryEmailAddress?.emailAddress ?? null, id: user.id } : null,
    selectedRole,
    profileLoading,
    profileError,
    reloadProfile,
    chooseRole,
    getToken,
    signOut,
  }), [clerkAuth.isLoaded, clerkAuth.isSignedIn, userId, user, selectedRole, profileLoading, profileError, reloadProfile, chooseRole, getToken, signOut]);
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const value = useContext(AuthContext);
  if (!value) throw new Error('AuthProvider is required.');
  return value;
}
