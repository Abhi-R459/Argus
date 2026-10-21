import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react';
import { useAuth as useClerkAuth, useUser } from '@clerk/react';
import { readWorkspaceRole, writeWorkspaceRole, type WorkspaceRole } from '../../lib/workspaceRole';

interface AuthState {
  isLoaded: boolean;
  isSignedIn: boolean;
  userId: string | null;
  user: { fullName: string | null; email: string | null; id: string } | null;
  selectedRole: WorkspaceRole | null;
  chooseRole: (role: WorkspaceRole) => void;
  getToken: (options?: { skipCache?: boolean }) => Promise<string | null>;
  signOut: () => Promise<void>;
}

const AuthContext = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const clerkAuth = useClerkAuth();
  const { user } = useUser();
  const [selectedRole, setSelectedRole] = useState<WorkspaceRole | null>(readWorkspaceRole);
  const userId = clerkAuth.userId ?? null;

  useEffect(() => {
    const previous = sessionStorage.getItem('argus:role-user');
    if (userId && previous && previous !== userId) {
      writeWorkspaceRole(null);
      setSelectedRole(null);
    }
    if (userId) sessionStorage.setItem('argus:role-user', userId);
  }, [userId]);

  const chooseRole = useCallback((role: WorkspaceRole) => {
    writeWorkspaceRole(role);
    setSelectedRole(role);
  }, []);
  const getToken = useCallback(
    (options?: { skipCache?: boolean }) => clerkAuth.getToken({ skipCache: options?.skipCache }),
    [clerkAuth],
  );
  const signOut = useCallback(async () => {
    writeWorkspaceRole(null);
    sessionStorage.removeItem('argus:role-user');
    setSelectedRole(null);
    await clerkAuth.signOut();
  }, [clerkAuth]);
  const value = useMemo(() => ({
    isLoaded: clerkAuth.isLoaded,
    isSignedIn: clerkAuth.isSignedIn ?? false,
    userId,
    user: user ? { fullName: user.fullName, email: user.primaryEmailAddress?.emailAddress ?? null, id: user.id } : null,
    selectedRole,
    chooseRole,
    getToken,
    signOut,
  }), [clerkAuth.isLoaded, clerkAuth.isSignedIn, userId, user, selectedRole, chooseRole, getToken, signOut]);
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const value = useContext(AuthContext);
  if (!value) throw new Error('AuthProvider is required.');
  return value;
}
