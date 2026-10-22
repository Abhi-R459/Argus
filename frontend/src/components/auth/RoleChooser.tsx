import { useState } from 'react';
import { useAuth } from './AuthProvider';
import type { WorkspaceRole } from '../../lib/workspaceRole';

export default function RoleChooser() {
  const { chooseRole } = useAuth();
  const [role, setRole] = useState<WorkspaceRole | null>(null);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const submit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!role) return;
    setSaving(true);
    setError(null);
    try { await chooseRole(role); }
    catch (cause) { setError(cause instanceof Error ? cause.message : 'Could not save your role.'); }
    finally { setSaving(false); }
  };
  return <main className="min-h-screen bg-linear-canvas text-linear-ink flex items-center justify-center p-4">
    <section className="w-full max-w-xl rounded-2xl border border-linear-border bg-linear-surface-1 p-7 shadow-sm">
      <p className="text-sm font-semibold text-linear-primary">Step 2 of 2</p>
      <h1 className="mt-2 text-2xl font-semibold">Choose your account role</h1>
      <p className="mt-2 text-sm text-linear-ink-subtle">Choose Auditor or HR once. Your account will keep this role permanently.</p>
      {error && <p role="alert" className="mt-4 text-sm text-status-danger">{error}</p>}
      <form onSubmit={(event) => void submit(event)}>
        <fieldset disabled={saving} className="mt-7 grid gap-3 sm:grid-cols-2">
          <legend className="sr-only">Account role</legend>
          <label className={`cursor-pointer rounded-xl border p-5 text-left focus-within:ring-2 focus-within:ring-linear-primary ${role === 'compliance_auditor' ? 'border-linear-primary bg-linear-primary/5' : 'border-linear-border hover:border-linear-primary'}`}>
            <input type="radio" name="role" value="compliance_auditor" checked={role === 'compliance_auditor'} onChange={() => setRole('compliance_auditor')} className="mb-3 accent-linear-primary" />
            <span className="block text-lg font-semibold">Auditor</span>
            <span className="mt-2 block text-sm text-linear-ink-subtle">Review records, investigate changes, and export evidence.</span>
          </label>
          <label className={`cursor-pointer rounded-xl border p-5 text-left focus-within:ring-2 focus-within:ring-linear-primary ${role === 'hr_admin' ? 'border-linear-primary bg-linear-primary/5' : 'border-linear-border hover:border-linear-primary'}`}>
            <input type="radio" name="role" value="hr_admin" checked={role === 'hr_admin'} onChange={() => setRole('hr_admin')} className="mb-3 accent-linear-primary" />
            <span className="block text-lg font-semibold">HR</span>
            <span className="mt-2 block text-sm text-linear-ink-subtle">Manage employees, compensation, and settings.</span>
          </label>
        </fieldset>
        <button type="submit" disabled={!role || saving} className="mt-6 w-full rounded-xl bg-linear-primary px-5 py-3 font-semibold text-white disabled:cursor-not-allowed disabled:opacity-50">
          {saving ? 'Saving your role…' : 'Confirm role and continue'}
        </button>
      </form>
    </section>
  </main>;
}
