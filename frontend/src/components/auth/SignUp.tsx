import { SignUp as ClerkSignUp } from '@clerk/react';
import { Link } from 'react-router-dom';
import AuthShell from './AuthShell';

export default function SignUp({ isLoaded }: { isLoaded: boolean }) {
  return <AuthShell eyebrow="Step 1 of 2 · Account" title="Create your Argus account" description="Verify your email to create an account. You will choose Auditor or HR next.">
    <div className="mb-6 flex rounded-xl border border-slate-200 bg-white p-1 text-sm font-semibold shadow-xs">
      <Link to="/" className="flex-1 rounded-lg px-3 py-2.5 text-center text-slate-600 hover:bg-slate-50 hover:text-slate-900">Sign in</Link>
      <span className="flex-1 rounded-lg bg-[#111827] px-3 py-2.5 text-center text-white">Create an account</span>
    </div>
    {isLoaded ? <ClerkSignUp routing="hash" signInUrl="/" fallbackRedirectUrl="/" /> : <div role="status">Loading sign-up form…</div>}
  </AuthShell>;
}
