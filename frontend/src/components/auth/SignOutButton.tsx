import { useState } from 'react';
import { useAuth } from './AuthProvider';

export default function SignOutButton({ children = 'Sign out' }: { children?: React.ReactNode }) {
  const { signOut } = useAuth();
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  async function handleSignOut() {
    setPending(true);
    setError(null);
    try { await signOut(); }
    catch { setError('Sign-out failed. Please try again.'); }
    finally { setPending(false); }
  }
  return <div>
    <button type="button" disabled={pending} onClick={() => void handleSignOut()}
      className="rounded-lg border border-current/20 px-3 py-2 text-xs font-medium hover:bg-current/5 disabled:opacity-60 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-linear-primary">
      {pending ? 'Signing out…' : children}
    </button>
    {error && <p role="alert" className="mt-1 max-w-48 text-xs text-status-warning">{error}</p>}
  </div>;
}
