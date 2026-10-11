import { useState } from 'react';
import { useAuth } from './AuthProvider';

export default function SignIn() {
  const { signIn, authError } = useAuth();
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  async function handleSignIn() {
    setPending(true);
    setError(null);
    try { await signIn(); }
    catch { setError('Google sign-in is unavailable. Please try again.'); setPending(false); }
  }
  return <section className="w-full max-w-sm rounded-2xl border border-linear-border bg-linear-surface-1 p-6 shadow-sm">
    <h2 className="font-semibold text-linear-ink">Welcome to Argus</h2>
    <p className="mt-2 text-sm text-linear-ink-subtle">Use your approved Google account to access your workspace.</p>
    {(error || authError) && <p role="alert" className="mt-4 text-sm text-status-warning">{error || authError}</p>}
    <button type="button" disabled={pending} onClick={() => void handleSignIn()}
      className="mt-5 w-full rounded-lg bg-linear-primary px-4 py-3 text-sm font-semibold text-white hover:bg-linear-primary-hover disabled:opacity-60 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-linear-primary focus-visible:ring-offset-2">
      {pending ? 'Opening Google…' : 'Continue with Google'}
    </button>
    <p className="mt-4 text-xs text-linear-ink-subtle">Access is restricted to accounts approved by your administrator.</p>
  </section>;
}
