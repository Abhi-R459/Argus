import { useUser, useClerk } from '@clerk/clerk-react';
import { ShieldCheck, Database, Key, User } from 'lucide-react';

export default function HRSettings() {
  const { user } = useUser();
  const { openUserProfile } = useClerk();

  return (
    <div className="animate-in fade-in slide-in-from-bottom-4 duration-500 space-y-8 max-w-4xl">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-slate-900 tracking-tight">System & Account Settings</h1>
        <p className="text-slate-500 text-sm mt-1">
          Review your security profile, PostgreSQL engine configuration, and identity parameters.
        </p>
      </div>

      {/* Profile Card */}
      <div className="bg-white rounded-xl shadow-sm border border-slate-200/80 p-6 space-y-6">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-slate-100 pb-6">
          <div className="flex items-center space-x-4">
            <img
              src={user?.imageUrl || 'https://images.unsplash.com/photo-1472099645785-5658abf4ff4e?w=100&h=100&fit=crop&crop=face'}
              alt="Avatar"
              className="w-14 h-14 rounded-full border-2 border-indigo-100 shadow-sm object-cover"
            />
            <div>
              <h2 className="text-lg font-bold text-slate-900">{user?.fullName || 'HR Administrator'}</h2>
              <p className="text-sm text-slate-500">{user?.primaryEmailAddress?.emailAddress || 'admin@argus.internal'}</p>
              <span className="inline-flex items-center px-2.5 py-0.5 mt-1.5 rounded-full text-xs font-semibold bg-indigo-50 text-indigo-700 border border-indigo-200">
                Current Role: HR Administrator
              </span>
            </div>
          </div>
          <button
            onClick={() => openUserProfile()}
            className="inline-flex items-center px-4 py-2 border border-slate-200 bg-white hover:bg-slate-50 text-slate-700 rounded-lg text-sm font-semibold shadow-sm transition-colors"
          >
            <User className="w-4 h-4 mr-2 text-slate-500" />
            Manage Account
          </button>
        </div>

        {/* Identity Details */}
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 text-sm">
          <div className="bg-slate-50 p-4 rounded-lg border border-slate-100">
            <span className="text-xs font-semibold uppercase text-slate-400">Clerk User ID</span>
            <p className="font-mono text-xs text-slate-700 mt-1 break-all">{user?.id || 'user_demo'}</p>
          </div>
          <div className="bg-slate-50 p-4 rounded-lg border border-slate-100">
            <span className="text-xs font-semibold uppercase text-slate-400">Two-Factor Authentication</span>
            <p className="text-xs font-medium text-slate-700 mt-1">
              {user?.twoFactorEnabled ? 'Enabled (Enforced)' : 'Configured via Clerk'}
            </p>
          </div>
        </div>
      </div>

      {/* Engine & Security Architecture */}
      <div className="bg-white rounded-xl shadow-sm border border-slate-200/80 p-6 space-y-6">
        <h3 className="font-bold text-slate-900 text-base flex items-center">
          <ShieldCheck className="w-5 h-5 mr-2 text-indigo-600" />
          Database Security & Cryptographic Posture
        </h3>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div className="p-4 rounded-xl border border-slate-100 bg-slate-50/50 space-y-2">
            <div className="flex items-center space-x-2 text-slate-700 font-semibold text-sm">
              <Database className="w-4 h-4 text-indigo-600" />
              <span>PostgreSQL Connection Pool</span>
            </div>
            <p className="text-xs text-slate-500 leading-relaxed">
              Connected via isolated <code className="text-indigo-600 font-mono">hr_admin</code> role pool. Raw access to audit mutation logs is strictly revoked at the database kernel level.
            </p>
          </div>

          <div className="p-4 rounded-xl border border-slate-100 bg-slate-50/50 space-y-2">
            <div className="flex items-center space-x-2 text-slate-700 font-semibold text-sm">
              <Key className="w-4 h-4 text-indigo-600" />
              <span>PII Column Encryption</span>
            </div>
            <p className="text-xs text-slate-500 leading-relaxed">
              National IDs and sensitive contacts are encrypted using AES-256 via <code className="text-indigo-600 font-mono">pgcrypto</code> and indexed via HMAC-SHA256 blind salts.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
