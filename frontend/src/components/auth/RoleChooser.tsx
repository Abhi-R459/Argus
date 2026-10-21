import { useAuth } from './AuthProvider';

export default function RoleChooser() {
  const { chooseRole } = useAuth();
  return <main className="min-h-screen bg-linear-canvas text-linear-ink flex items-center justify-center p-4">
    <section className="w-full max-w-xl rounded-2xl border border-linear-border bg-linear-surface-1 p-7 shadow-sm">
      <h1 className="text-2xl font-semibold">Choose your workspace</h1>
      <p className="mt-2 text-sm text-linear-ink-subtle">You can change workspaces at any time.</p>
      <div className="mt-7 grid gap-3 sm:grid-cols-2">
        <button type="button" onClick={() => chooseRole('compliance_auditor')}
          className="rounded-xl border border-linear-border p-5 text-left hover:border-linear-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-linear-primary">
          <span className="block text-lg font-semibold">Auditor</span>
          <span className="mt-2 block text-sm text-linear-ink-subtle">Review records, investigate changes, and export evidence.</span>
        </button>
        <button type="button" onClick={() => chooseRole('hr_admin')}
          className="rounded-xl border border-linear-border p-5 text-left hover:border-linear-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-linear-primary">
          <span className="block text-lg font-semibold">HR</span>
          <span className="mt-2 block text-sm text-linear-ink-subtle">Manage employees, compensation, and settings.</span>
        </button>
      </div>
    </section>
  </main>;
}
