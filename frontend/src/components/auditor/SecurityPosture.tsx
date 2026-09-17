import { useQuery } from '@tanstack/react-query';
import { useAuth } from '@clerk/clerk-react';
import { Shield, Lock, Key, CheckCircle2, XCircle, Loader2 } from 'lucide-react';
import { fetchSystemMetrics, type SystemMetrics } from '../../services/auditService';
import RefreshButton from '../common/RefreshButton';

export default function SecurityPosture() {
  const { getToken } = useAuth();

  const { data, isLoading, refetch } = useQuery<SystemMetrics>({
    queryKey: ['systemMetrics'],
    queryFn: () => fetchSystemMetrics(() => getToken()),
    refetchInterval: 4000,
  });

  const score = data?.security_score ?? (isLoading ? 0 : 70);
  const grade = score >= 95 ? 'Grade A+' : score >= 85 ? 'Grade A' : score >= 70 ? 'Grade B' : 'Grade C';

  return (
    <div className="bg-[#0F172A]/80 border border-slate-800/80 rounded-2xl overflow-hidden shadow-sm animate-fade-cascade">
      <div className="px-6 py-5 border-b border-slate-800/80 bg-[#0B0F17]/50 flex items-center justify-between">
        <div className="flex items-center space-x-3">
          <div className="p-2 bg-emerald-500/10 rounded-lg border border-emerald-500/20">
            <Shield className="w-5 h-5 text-emerald-400" />
          </div>
          <div>
            <h3 className="text-base font-semibold text-slate-100">Security & Isolation Posture</h3>
            <p className="text-xs text-slate-400 mt-0.5">Automated verification of database security boundaries</p>
          </div>
        </div>
        <RefreshButton
          onRefresh={() => refetch()}
          variant="icon-dark"
          title="Re-verify posture"
        />
      </div>

      <div className="p-6 grid grid-cols-1 md:grid-cols-2 gap-8">
        {/* Overall Score */}
        <div className="flex flex-col items-center justify-center border-r border-slate-800/80 pr-8">
          <div className="relative flex items-center justify-center w-40 h-40">
            <svg className="w-full h-full transform -rotate-90" viewBox="0 0 36 36">
              <path
                className="text-slate-800/80"
                strokeWidth="3"
                stroke="currentColor"
                fill="none"
                d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831"
              />
              <path
                className={`${
                  score >= 85 ? 'text-emerald-400' : score >= 70 ? 'text-amber-400' : 'text-rose-400'
                } transition-[stroke-dasharray] duration-700 ease-out`}
                strokeWidth="3"
                strokeDasharray={`${score}, 100`}
                strokeLinecap="round"
                stroke="currentColor"
                fill="none"
                d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831"
              />
            </svg>
            <div className="absolute flex flex-col items-center justify-center">
              {isLoading ? (
                <Loader2 className="w-8 h-8 text-slate-400 animate-fast-spin" />
              ) : (
                <>
                  <span className="text-4xl font-black text-slate-100 font-mono">{score}</span>
                  <span className="text-[10px] uppercase font-bold text-slate-400 tracking-widest mt-1">
                    {grade}
                  </span>
                </>
              )}
            </div>
          </div>
          <p className="text-sm text-slate-400 text-center mt-4">
            Security score computed dynamically from PostgreSQL privilege checks and cryptographic integrity.
          </p>
        </div>

        {/* Configuration Checklist */}
        <div className="flex flex-col justify-center space-y-5">
          {/* Role Isolation */}
          <div className="flex items-start space-x-3">
            <div className={`mt-0.5 w-6 h-6 rounded flex items-center justify-center flex-shrink-0 ${
              data?.security_checks?.role_isolation
                ? 'bg-emerald-500/10 border border-emerald-500/20 text-emerald-400'
                : 'bg-rose-500/10 border border-rose-500/20 text-rose-400'
            }`}>
              {data?.security_checks?.role_isolation ? (
                <CheckCircle2 className="w-3.5 h-3.5" />
              ) : (
                <Lock className="w-3.5 h-3.5" />
              )}
            </div>
            <div>
              <p className="text-sm font-semibold text-slate-200 flex items-center gap-2">
                Role Segregation
                {data?.security_checks?.role_isolation && (
                  <span className="text-[10px] font-mono uppercase bg-emerald-500/10 text-emerald-400 px-1.5 py-0.2 rounded border border-emerald-500/20">Verified</span>
                )}
              </p>
              <p className="text-xs text-slate-400 mt-0.5">
                PostgreSQL role <code className="text-violet-300 bg-violet-500/10 px-1 py-0.5 rounded">hr_admin</code> has NO direct UPDATE/DELETE privileges on <code className="text-violet-300 bg-violet-500/10 px-1 py-0.5 rounded">audit_log</code>.
              </p>
            </div>
          </div>

          {/* Cryptographic Extension */}
          <div className="flex items-start space-x-3">
            <div className={`mt-0.5 w-6 h-6 rounded flex items-center justify-center flex-shrink-0 ${
              data?.security_checks?.pgcrypto_active
                ? 'bg-emerald-500/10 border border-emerald-500/20 text-emerald-400'
                : 'bg-rose-500/10 border border-rose-500/20 text-rose-400'
            }`}>
              {data?.security_checks?.pgcrypto_active ? (
                <CheckCircle2 className="w-3.5 h-3.5" />
              ) : (
                <Key className="w-3.5 h-3.5" />
              )}
            </div>
            <div>
              <p className="text-sm font-semibold text-slate-200 flex items-center gap-2">
                Cryptographic Extension
                {data?.security_checks?.pgcrypto_active && (
                  <span className="text-[10px] font-mono uppercase bg-emerald-500/10 text-emerald-400 px-1.5 py-0.2 rounded border border-emerald-500/20">Active</span>
                )}
              </p>
              <p className="text-xs text-slate-400 mt-0.5">
                <code className="text-violet-300 bg-violet-500/10 px-1 py-0.5 rounded">pgcrypto</code> is loaded and computes HMAC-SHA256 digests in database triggers.
              </p>
            </div>
          </div>

          {/* Chain Tail Continuity */}
          <div className="flex items-start space-x-3">
            <div className={`mt-0.5 w-6 h-6 rounded flex items-center justify-center flex-shrink-0 ${
              data?.security_checks?.chain_continuous
                ? 'bg-emerald-500/10 border border-emerald-500/20 text-emerald-400'
                : 'bg-rose-500/10 border border-rose-500/20 text-rose-400'
            }`}>
              {data?.security_checks?.chain_continuous ? (
                <CheckCircle2 className="w-3.5 h-3.5" />
              ) : (
                <XCircle className="w-3.5 h-3.5" />
              )}
            </div>
            <div>
              <p className="text-sm font-semibold text-slate-200 flex items-center gap-2">
                Chain State Continuity
                {data?.security_checks?.chain_continuous && (
                  <span className="text-[10px] font-mono uppercase bg-emerald-500/10 text-emerald-400 px-1.5 py-0.2 rounded border border-emerald-500/20">Synchronized</span>
                )}
              </p>
              <p className="text-xs text-slate-400 mt-0.5">
                Tail checkpoint sequence matches the latest entry in <code className="text-violet-300 bg-violet-500/10 px-1 py-0.5 rounded">audit_log</code>.
              </p>
            </div>
          </div>
        </div>

      </div>
    </div>
  );
}
