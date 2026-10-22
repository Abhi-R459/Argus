import type { ReactNode } from 'react';
import { Activity, ArrowUpRight, Fingerprint, ShieldCheck } from 'lucide-react';

interface AuthShellProps {
  title: string;
  description: string;
  eyebrow: string;
  children: ReactNode;
}

export default function AuthShell({ title, description, eyebrow, children }: AuthShellProps) {
  return <main className="min-h-screen bg-[#f5f7fb] text-[#142033] lg:grid lg:grid-cols-[minmax(0,1.05fr)_minmax(440px,0.95fr)]">
    <aside className="relative hidden min-h-screen flex-col justify-between overflow-hidden bg-[#111827] px-12 py-11 text-white lg:flex xl:px-16">
      <div className="pointer-events-none absolute -right-32 -top-32 h-[520px] w-[520px] rounded-full bg-blue-500/15 blur-3xl" aria-hidden="true" />
      <div className="pointer-events-none absolute inset-0 opacity-[0.08] [background-image:linear-gradient(#fff_1px,transparent_1px),linear-gradient(90deg,#fff_1px,transparent_1px)] [background-size:48px_48px]" aria-hidden="true" />
      <div className="relative flex items-center gap-3">
        <span className="flex h-11 w-11 items-center justify-center rounded-xl border border-blue-400/30 bg-blue-500/15 text-blue-300">
          <ShieldCheck className="h-6 w-6" aria-hidden="true" />
        </span>
        <div>
          <p className="text-lg font-semibold tracking-tight">Argus</p>
          <p className="text-[11px] font-medium uppercase tracking-[0.24em] text-slate-300">Audit operations</p>
        </div>
      </div>

      <div className="relative max-w-xl pb-12">
        <div className="mb-8 inline-flex items-center gap-2 rounded-full border border-blue-400/25 bg-blue-500/10 px-3 py-1.5 text-xs font-medium text-blue-200">
          <Activity className="h-3.5 w-3.5" aria-hidden="true" />
          A clear view of every change
        </div>
        <h2 className="max-w-lg text-5xl font-semibold leading-[1.08] tracking-[-0.045em] xl:text-6xl">
          People data.<br /><span className="text-blue-300">Accountable actions.</span>
        </h2>
        <p className="mt-6 max-w-md text-base leading-7 text-slate-300">
          Manage personnel records and follow the audit trail from one secure workspace.
        </p>
        <div className="mt-12 rounded-2xl border border-white/15 bg-white/[0.06] p-5 backdrop-blur-sm">
          <div className="flex items-center justify-between border-b border-white/10 pb-4">
            <div className="flex items-center gap-3">
              <span className="flex h-9 w-9 items-center justify-center rounded-lg bg-blue-500/20 text-blue-200"><Fingerprint className="h-5 w-5" aria-hidden="true" /></span>
              <div>
                <p className="text-sm font-semibold">One account, one workspace</p>
                <p className="mt-0.5 text-xs text-slate-300">Choose Auditor or HR during setup</p>
              </div>
            </div>
            <ArrowUpRight className="h-4 w-4 text-blue-300" aria-hidden="true" />
          </div>
          <div className="mt-4 flex items-center gap-3 text-xs text-slate-300">
            <span className="h-2 w-2 rounded-full bg-emerald-400" />
            Your role is saved to your account after you choose it.
          </div>
        </div>
      </div>

      <p className="relative text-xs text-slate-400">Argus · Secure workforce and audit workspace</p>
    </aside>

    <section className="flex min-h-screen flex-col px-5 py-7 sm:px-10 lg:px-12 lg:py-11" aria-label="Argus account access">
      <div className="flex items-center gap-2 lg:hidden">
        <span className="flex h-9 w-9 items-center justify-center rounded-lg bg-[#111827] text-blue-300"><ShieldCheck className="h-5 w-5" aria-hidden="true" /></span>
        <span className="font-semibold tracking-tight">Argus</span>
      </div>
      <div className="mx-auto flex w-full max-w-[430px] flex-1 flex-col justify-center py-12 lg:py-0">
        <p className="text-xs font-bold uppercase tracking-[0.22em] text-blue-700">{eyebrow}</p>
        <h1 className="mt-3 text-3xl font-semibold tracking-[-0.035em] sm:text-4xl">{title}</h1>
        <p className="mt-3 max-w-sm text-sm leading-6 text-slate-600">{description}</p>
        <div className="mt-8">{children}</div>
      </div>
      <p className="mx-auto w-full max-w-[430px] text-xs text-slate-500">Protected by Clerk authentication and Argus role controls.</p>
    </section>
  </main>;
}
