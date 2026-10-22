import { SignUp as ClerkSignUp } from '@clerk/react';
import { Link } from 'react-router-dom';

export default function SignUp({ isLoaded }: { isLoaded: boolean }) {
  return <main className="min-h-screen bg-linear-canvas text-linear-ink flex flex-col items-center justify-center p-4">
    <div className="mb-6 max-w-md text-center">
      <p className="text-sm font-semibold text-linear-primary">Step 1 of 2</p>
      <h1 className="mt-2 text-3xl font-bold">Create your Argus account</h1>
      <p className="mt-2 text-sm text-linear-ink-subtle">Verify your email to create an account. You will choose Auditor or HR next.</p>
    </div>
    {isLoaded ? <ClerkSignUp routing="hash" signInUrl="/" fallbackRedirectUrl="/" /> : <div role="status">Loading sign-up form…</div>}
    <Link to="/" className="mt-5 text-sm font-medium text-linear-primary underline">Already have an account? Sign in</Link>
  </main>;
}
