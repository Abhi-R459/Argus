import { RefreshCw } from 'lucide-react';
import { SignOutButton } from '@clerk/clerk-react';

interface ProfileLoadErrorProps {
  onRetry: () => void;
}

export default function ProfileLoadError({ onRetry }: ProfileLoadErrorProps) {
  return (
    <main className="min-h-screen bg-linear-canvas flex items-center justify-center p-4 text-linear-ink">
      <section className="w-full max-w-md rounded-2xl border border-status-warning/35 bg-linear-surface-1 p-6 shadow-sm" role="alert">
        <h1 className="text-lg font-semibold">Unable to verify your account</h1>
        <p className="mt-2 text-sm text-linear-ink-subtle">
          Argus could not load your profile or portal permissions. Check your connection and try again. If you signed in with the wrong account, sign out and use an allowlisted demo account.
        </p>
        <div className="mt-5 flex flex-wrap gap-3">
          <button
            type="button"
            onClick={onRetry}
            className="inline-flex items-center gap-2 rounded-lg bg-linear-primary px-4 py-2 text-sm font-medium text-white hover:bg-linear-primary-hover focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-linear-primary focus-visible:ring-offset-2 focus-visible:ring-offset-linear-canvas"
          >
            <RefreshCw className="h-4 w-4" /> Retry
          </button>
          <SignOutButton signOutOptions={{ redirectUrl: '/' }}>
            <button
              type="button"
              className="inline-flex items-center rounded-lg border border-linear-border px-4 py-2 text-sm font-medium text-linear-ink hover:bg-linear-surface-2 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-linear-primary focus-visible:ring-offset-2 focus-visible:ring-offset-linear-canvas"
            >
              Sign out and switch account
            </button>
          </SignOutButton>
        </div>
      </section>
    </main>
  );
}
