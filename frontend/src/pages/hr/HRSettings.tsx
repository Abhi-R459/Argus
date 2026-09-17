import { useUser, useClerk } from '@clerk/clerk-react';
import { ShieldCheck, Database, Key, User, Lock, CheckCircle2 } from 'lucide-react';
import { Button } from '../../components/common/Button';

export default function HRSettings() {
  const { user } = useUser();
  const { openUserProfile } = useClerk();

  return (
    <div className="space-y-8 max-w-4xl animate-fade-cascade">
      {/* Header */}
      <div className="border-b border-grafana-border pb-5">
        <h1 className="text-xl font-bold text-black tracking-tight">Security & Access Management</h1>
        <p className="text-xs text-grafana-neutral mt-1">
          Cryptographic keys, Clerk authentication tokens, role-based access control, and PostgreSQL session parameters.
        </p>
      </div>

      {/* Clerk Profile & Session Card */}
      <div className="bg-white rounded-2xl border border-grafana-border p-6 shadow-sm space-y-6">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-6 border-b border-grafana-border">
          <div className="flex items-center space-x-4">
            <div className="w-12 h-12 rounded-xl bg-grafana-orange/10 border border-grafana-orange/20 flex items-center justify-center text-grafana-orange font-bold text-base shadow-2xs">
              {user?.firstName ? user.firstName[0] : 'U'}
            </div>
            <div>
              <div className="flex items-center space-x-2">
                <h3 className="text-base font-bold text-grafana-ink">{user?.fullName || 'HR Administrator'}</h3>
                <span className="px-2 py-0.5 rounded text-[10px] font-mono font-semibold bg-emerald-50 text-emerald-800 border border-emerald-200/80">
                  HR Admin
                </span>
              </div>
              <p className="text-xs text-grafana-neutral font-mono mt-0.5">{user?.primaryEmailAddress?.emailAddress || 'hr@argustech.com'}</p>
              <div className="mt-1.5 flex items-center space-x-2">
                <span className="inline-flex items-center space-x-1 text-[11px] text-linear-success font-medium">
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
            leftIcon={<User className="w-3.5 h-3.5 text-grafana-neutral" />}
          >
            Manage Account
          </Button>
        </div>

        {/* Identity Details */}
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 text-sm">
          <div className="bg-grafana-surface p-4 rounded-xl border border-grafana-border">
            <span className="text-[10px] font-bold uppercase tracking-wider text-grafana-neutral">Clerk User Identifier</span>
            <p className="font-mono text-xs text-grafana-ink mt-1.5 break-all select-all font-semibold bg-white p-2 rounded-lg border border-grafana-border shadow-2xs">
              {user?.id || 'user_demo'}
            </p>
          </div>
          <div className="bg-grafana-surface p-4 rounded-xl border border-grafana-border flex flex-col justify-between">
            <span className="text-[10px] font-bold uppercase tracking-wider text-grafana-neutral">Two-Factor Authentication</span>
            <div className="mt-1.5 flex items-center space-x-2 bg-white p-2 rounded-lg border border-grafana-border shadow-2xs">
              <Lock className="w-4 h-4 text-linear-success shrink-0" />
              <span className="text-xs font-semibold text-grafana-ink">
                {user?.twoFactorEnabled ? 'Enabled & Enforced' : 'Active (Clerk MFA Enforced)'}
              </span>
            </div>
          </div>
        </div>
      </div>

      {/* Engine & Security Architecture */}
      <div className="card-hover bg-white rounded-xl shadow-xs border border-grafana-border p-6 space-y-6 relative overflow-hidden">
        <div className="absolute top-0 left-0 right-0 h-1 bg-gradient-to-r from-grafana-blue to-grafana-blue/70" />
        <div className="flex items-center space-x-2.5">
          <div className="p-2 rounded-lg bg-grafana-blue/10 text-grafana-blue border border-grafana-blue/20">
            <ShieldCheck className="w-5 h-5" />
          </div>
          <div>
            <h3 className="font-bold text-grafana-ink text-sm tracking-tight">
              Database Security & Cryptographic Posture
            </h3>
            <p className="text-xs text-grafana-neutral">PostgreSQL kernel security invariants and encryption state</p>
          </div>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div className="p-4 rounded-xl border border-grafana-border bg-grafana-surface space-y-2 hover:bg-grafana-surface/80 transition-colors">
            <div className="flex items-center space-x-2 text-grafana-ink font-semibold text-xs">
              <Database className="w-4 h-4 text-grafana-blue" />
              <span>PostgreSQL Connection Pool</span>
            </div>
            <p className="text-xs text-grafana-neutral leading-relaxed">
              Connected via isolated <code className="text-grafana-blue font-mono text-[11px] bg-grafana-blue/10 px-1.5 py-0.5 rounded border border-grafana-blue/20 font-semibold">hr_admin</code> role pool. Raw access to audit mutation logs is strictly revoked at the database kernel level.
            </p>
          </div>

          <div className="p-4 rounded-xl border border-grafana-border bg-grafana-surface space-y-2 hover:bg-grafana-surface/80 transition-colors">
            <div className="flex items-center space-x-2 text-grafana-ink font-semibold text-xs">
              <Key className="w-4 h-4 text-linear-success" />
              <span>PII Column Encryption</span>
            </div>
            <p className="text-xs text-grafana-neutral leading-relaxed">
              National IDs and sensitive contacts are encrypted using AES-256 via <code className="text-linear-success font-mono text-[11px] bg-linear-success/10 px-1.5 py-0.5 rounded border border-linear-success/20 font-semibold">pgcrypto</code> and indexed via HMAC-SHA256 blind salts.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}

