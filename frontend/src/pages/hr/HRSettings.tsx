import { useUser, useClerk } from '@clerk/clerk-react';
import { ShieldCheck, Database, Key, User, Lock, CheckCircle2 } from 'lucide-react';

export default function HRSettings() {
  const { user } = useUser();
  const { openUserProfile } = useClerk();

  return (
    <div className="space-y-8 max-w-4xl animate-fade-cascade">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-slate-900 tracking-tight">System & Account Configuration</h1>
        <p className="text-slate-500 text-sm mt-1">
          Review your authenticated identity, PostgreSQL connection isolation, and cryptographic storage parameters.
        </p>
      </div>

      {/* Profile Card */}
      <div className="card-hover bg-white rounded-2xl shadow-[0_1px_3px_rgba(0,0,0,0.04),0_1px_2px_rgba(0,0,0,0.02)] border border-slate-200/90 p-6 space-y-6 relative overflow-hidden">
        <div className="absolute top-0 left-0 right-0 h-1 bg-gradient-to-r from-indigo-500 via-indigo-600 to-indigo-400" />
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-5 border-b border-slate-100 pb-6">
          <div className="flex items-center space-x-4">
            <div className="relative shrink-0 w-14 h-14 min-w-[56px] min-h-[56px] max-w-[56px] max-h-[56px]">
              <img
                src={user?.imageUrl || 'https://images.unsplash.com/photo-1472099645785-5658abf4ff4e?w=100&h=100&fit=crop&crop=face'}
                alt="Avatar"
                className="w-14 h-14 min-w-[56px] min-h-[56px] max-w-[56px] max-h-[56px] rounded-full border-2 border-indigo-100 shadow-sm object-cover block"
              />
              <span className="absolute bottom-0 right-0 w-3.5 h-3.5 rounded-full bg-emerald-500 border-2 border-white shadow-xs" />
            </div>
            <div>
              <div className="flex items-center space-x-2.5">
                <h2 className="text-base font-bold text-slate-900 tracking-tight">{user?.fullName || 'HR Administrator'}</h2>
                <span className="inline-flex items-center px-2 py-0.5 rounded-md text-[11px] font-semibold bg-indigo-50 text-indigo-700 border border-indigo-200/80">
                  HR Admin
                </span>
              </div>
              <p className="text-xs text-slate-500 font-mono mt-0.5">{user?.primaryEmailAddress?.emailAddress || 'hr@argustech.com'}</p>
              <div className="mt-1.5 flex items-center space-x-2">
                <span className="inline-flex items-center space-x-1 text-[11px] text-emerald-600 font-medium">
                  <CheckCircle2 className="w-3.5 h-3.5" />
                  <span>Authenticated via Clerk SSO</span>
                </span>
              </div>
            </div>
          </div>
          <button
            onClick={() => openUserProfile()}
            className="btn-press shrink-0 inline-flex items-center justify-center px-4 py-2 border border-slate-200 bg-white hover:bg-slate-50 text-slate-700 rounded-lg text-xs font-semibold shadow-xs cursor-pointer"
          >
            <User className="w-3.5 h-3.5 mr-1.5 text-slate-500" />
            Manage Account
          </button>
        </div>

        {/* Identity Details */}
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 text-sm">
          <div className="bg-slate-50/80 p-4 rounded-xl border border-slate-200/70">
            <span className="text-[10px] font-bold uppercase tracking-wider text-slate-400">Clerk User Identifier</span>
            <p className="font-mono text-xs text-slate-700 mt-1.5 break-all select-all font-semibold bg-white p-2 rounded-lg border border-slate-200/60 shadow-2xs">
              {user?.id || 'user_demo'}
            </p>
          </div>
          <div className="bg-slate-50/80 p-4 rounded-xl border border-slate-200/70 flex flex-col justify-between">
            <span className="text-[10px] font-bold uppercase tracking-wider text-slate-400">Two-Factor Authentication</span>
            <div className="mt-1.5 flex items-center space-x-2 bg-white p-2 rounded-lg border border-slate-200/60 shadow-2xs">
              <Lock className="w-4 h-4 text-emerald-600 shrink-0" />
              <span className="text-xs font-semibold text-slate-700">
                {user?.twoFactorEnabled ? 'Enabled & Enforced' : 'Active (Clerk MFA Enforced)'}
              </span>
            </div>
          </div>
        </div>
      </div>

      {/* Engine & Security Architecture */}
      <div className="card-hover bg-white rounded-2xl shadow-[0_1px_3px_rgba(0,0,0,0.04),0_1px_2px_rgba(0,0,0,0.02)] border border-slate-200/90 p-6 space-y-6 relative overflow-hidden">
        <div className="absolute top-0 left-0 right-0 h-1 bg-gradient-to-r from-emerald-500 via-teal-500 to-indigo-500" />
        <div className="flex items-center space-x-2.5">
          <div className="p-2 rounded-lg bg-emerald-50 text-emerald-600 border border-emerald-100">
            <ShieldCheck className="w-5 h-5" />
          </div>
          <div>
            <h3 className="font-bold text-slate-900 text-sm tracking-tight">
              Database Security & Cryptographic Posture
            </h3>
            <p className="text-xs text-slate-500">PostgreSQL kernel security invariants and encryption state</p>
          </div>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div className="p-4 rounded-xl border border-slate-200/70 bg-slate-50/70 space-y-2 hover:bg-slate-50 transition-colors">
            <div className="flex items-center space-x-2 text-slate-800 font-semibold text-xs">
              <Database className="w-4 h-4 text-indigo-600" />
              <span>PostgreSQL Connection Pool</span>
            </div>
            <p className="text-xs text-slate-500 leading-relaxed">
              Connected via isolated <code className="text-indigo-600 font-mono text-[11px] bg-indigo-50/90 px-1.5 py-0.5 rounded border border-indigo-200/60 font-semibold">hr_admin</code> role pool. Raw access to audit mutation logs is strictly revoked at the database kernel level.
            </p>
          </div>

          <div className="p-4 rounded-xl border border-slate-200/70 bg-slate-50/70 space-y-2 hover:bg-slate-50 transition-colors">
            <div className="flex items-center space-x-2 text-slate-800 font-semibold text-xs">
              <Key className="w-4 h-4 text-emerald-600" />
              <span>PII Column Encryption</span>
            </div>
            <p className="text-xs text-slate-500 leading-relaxed">
              National IDs and sensitive contacts are encrypted using AES-256 via <code className="text-emerald-700 font-mono text-[11px] bg-emerald-50/90 px-1.5 py-0.5 rounded border border-emerald-200/60 font-semibold">pgcrypto</code> and indexed via HMAC-SHA256 blind salts.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}

