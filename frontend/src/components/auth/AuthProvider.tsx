import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react';
import type { Session, User } from '@supabase/supabase-js';
import { supabase } from '../../lib/supabase';

interface AuthState {
  isLoaded: boolean;
  isSignedIn: boolean;
  userId: string | null;
  user: User | null;
  authError: string | null;
  getToken: (options?: { skipCache?: boolean }) => Promise<string | null>;
  signIn: () => Promise<void>;
  signOut: () => Promise<void>;
}
const AuthContext = createContext<AuthState | null>(null);
let refreshing: Promise<string | null> | null = null;

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [session, setSession] = useState<Session | null>(null);
  const [isLoaded, setIsLoaded] = useState(false);
  const [authError, setAuthError] = useState<string | null>(null);
  useEffect(() => {
    let active = true;
    const { data: { subscription } } = supabase.auth.onAuthStateChange((_event, nextSession) => {
      if (active) setSession(nextSession);
    });
    void (async () => {
      try {
        const initialization = await supabase.auth.initialize();
        if (initialization.error) throw initialization.error;
        const { data, error } = await supabase.auth.getSession();
        if (error) throw error;
        if (active) setSession(data.session);
      } catch {
        if (active) setAuthError('Sign-in could not be completed. Please try again.');
      } finally {
        // Remove authorization codes and provider errors from browser history.
        if (window.location.pathname === '/auth/callback') {
          window.history.replaceState(null, '', '/auth/callback');
        }
        if (active) setIsLoaded(true);
      }
    })();
    return () => { active = false; subscription.unsubscribe(); };
  }, []);
  const getToken = useCallback(async (options?: { skipCache?: boolean }) => {
    const { data, error } = await supabase.auth.getSession();
    if (error || !data.session) return null;
    if (!options?.skipCache) return data.session.access_token;
    // Concurrent 401 responses share one refresh, avoiding refresh-token reuse.
    refreshing ??= supabase.auth.refreshSession().then(({ data: next, error: failure }) =>
      failure ? null : next.session?.access_token ?? null
    ).finally(() => { refreshing = null; });
    return refreshing;
  }, []);
  const signIn = useCallback(async () => {
    setAuthError(null);
    const { error } = await supabase.auth.signInWithOAuth({ provider: 'google', options: {
      redirectTo: window.location.origin + '/auth/callback', queryParams: { prompt: 'select_account' },
    } });
    if (error) throw new Error('Google sign-in is unavailable. Please try again.');
  }, []);
  const signOut = useCallback(async () => {
    const { error } = await supabase.auth.signOut({ scope: 'local' });
    if (error) throw new Error('Sign-out could not be confirmed. Please try again.');
    setSession(null);
    setAuthError(null);
  }, []);
  const value = useMemo(() => ({ isLoaded, isSignedIn: !!session, userId: session?.user.id ?? null,
    user: session?.user ?? null, authError, getToken, signIn, signOut }),
  [isLoaded, session, authError, getToken, signIn, signOut]);
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}
export function useAuth() {
  const value = useContext(AuthContext);
  if (!value) throw new Error('AuthProvider is required.');
  return value;
}
