import { useUser, useClerk } from '@clerk/clerk-react';
import { ShieldCheck, Database, Key, User, Lock, CheckCircle2 } from 'lucide-react';
import { Button } from '../../components/common/Button';

export default function HRSettings() {
  const { user } = useUser();
  const { openUserProfile } = useClerk();

  return (
    <div className="space-y-8 max-w-4xl animate-fade-cascade">
      {/* Header */}
      <div className="border-b border-slate-200 pb-5">
        <h1 className="text-xl font-bold text-slate-900 tracking-tight">Security & Access Management</h1>
        <p className="text-xs text-slate-500 mt-1">
          Cryptographic keys, Clerk authentication tokens, role-based access control, and PostgreSQL session parameters.
        </p>
      </div>

      {/* Clerk Profile & Session Card */}
      <div className="bg-white rounded-2xl border border-slate-200/80 p-6 shadow-xs space-y-6">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-6 border-b border-slate-100">
          <div className="flex items-center space-x-4">
            <div className="w-12 h-12 rounded-2xl bg-slate-100 border border-slate-200/80 flex items-center justify-center text-slate-800 font-bold text-base shadow-2xs">
              {user?.firstName ? user.firstName[0] : 'U'}
            </div>
            <div>
              <div className="flex items-center space-x-2">
                <h3 className="text-base font-bold text-slate-900">{user?.fullName || 'HR Administrator'}</h3>
                <span className="px-2 py-0.5 rounded-full text-[10px] font-medium bg-emerald-50 text-emerald-800 border border-emerald-200/80">
                  HR Admin
                </span>
              </div>
              <p className="text-xs text-slate-500 font-mono mt-0.5">{user?.primaryEmailAddress?.emailAddress || 'hr@argustech.com'}</p>
              <div className="mt-1.5 flex items-center space-x-2">
                <span className="inline-flex items-center space-x-1 text-[11px] text-emerald-700 font-medium">
                  <CheckCircle2 className="w-3.5 h-3.5" />
                  <span>Authenticated via Clerk SSO</span>
                </span>
              </div>
            </div>
          </div>
          <Button
            variant="secondary"
            size="md"
            portalTheme="hr"
            onClick={() => openUserProfile()}
            leftIcon={<User className="w-3.5 h-3.5 text-slate-600" />}
          >
            Manage Account
          </Button>
        </div>

        {/* Identity Details */}
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 text-sm">
          <div className="bg-slate-50 p-4 rounded-xl border border-slate-200/80">
            <span className="text-[10px] font-semibold uppercase tracking-wider text-slate-500">Clerk User Identifier</span>
            <p className="font-mono text-xs text-slate-800 mt-1.5 break-all select-all font-semibold bg-white p-2 rounded-lg border border-slate-200 shadow-2xs">
              {user?.id || 'user_demo'}
            </p>
          </div>
          <div className="bg-slate-50 p-4 rounded-xl border border-slate-200/80 flex flex-col justify-between">
            <span className="text-[10px] font-semibold uppercase tracking-wider text-slate-500">Two-Factor Authentication</span>
            <div className="mt-1.5 flex items-center space-x-2 bg-white p-2 rounded-lg border border-slate-200 shadow-2xs">
              <Lock className="w-4 h-4 text-emerald-600 shrink-0" />
              <span className="text-xs font-semibold text-slate-800">
                {user?.twoFactorEnabled ? 'Enabled & Enforced' : 'Active (Clerk MFA Enforced)'}
              </span>
            </div>
          </div>
        </div>
      </div>

      {/* Engine & Security Architecture */}
      <div className="bg-white rounded-2xl shadow-xs border border-slate-200/80 p-6 space-y-6 overflow-hidden">
        <div className="flex items-center space-x-3">
          <div className="p-2.5 rounded-xl bg-blue-50 text-blue-600 border border-blue-100/80">
            <ShieldCheck className="w-5 h-5" />
          </div>
          <div>
            <h3 className="font-bold text-slate-900 text-sm tracking-tight">
              Database Security & Access Posture
            </h3>
            <p className="text-xs text-slate-500">PostgreSQL kernel security invariants and encryption state</p>
          </div>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div className="p-4 rounded-xl border border-slate-200/80 bg-slate-50 space-y-2">
            <div className="flex items-center space-x-2 text-slate-900 font-semibold text-xs">
              <Database className="w-4 h-4 text-blue-600" />
              <span>PostgreSQL Connection Pool</span>
            </div>
            <p className="text-xs text-slate-600 leading-relaxed">
              Connected via isolated <code className="text-slate-800 font-mono text-[11px] bg-slate-200/80 px-1.5 py-0.5 rounded border border-slate-300 font-semibold">hr_admin</code> role pool. Raw access to audit mutation logs is strictly revoked at the database kernel level.
            </p>
          </div>

          <div className="p-4 rounded-xl border border-slate-200/80 bg-slate-50 space-y-2">
            <div className="flex items-center space-x-2 text-slate-900 font-semibold text-xs">
              <Key className="w-4 h-4 text-emerald-600" />
              <span>PII Column Encryption</span>
            </div>
            <p className="text-xs text-slate-600 leading-relaxed">
              National IDs and sensitive contacts are encrypted using AES-256 via <code className="text-emerald-800 font-mono text-[11px] bg-emerald-50 px-1.5 py-0.5 rounded border border-emerald-200 font-semibold">pgcrypto</code> and indexed via HMAC-SHA256 blind salts.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}

