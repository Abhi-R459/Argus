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
  });

  const score = data?.security_score ?? (isLoading ? 0 : 70);
  const integrityCheckNames = [
    'verified_hash_chain',
    'verified_external_anchor',
    'verified_checkpoint_signatures',
    'independent_witness_quorum',
  ];
  const integrityChecks = data?.security_check_details ?? {};
  const hasIntegrityFailure = integrityCheckNames.some((name) => integrityChecks[name] === 'fail');
  const hasUnverifiedIntegrity = integrityCheckNames.some((name) => integrityChecks[name] === 'unknown');
  const grade = hasIntegrityFailure
    ? 'Check Failed'
    : hasUnverifiedIntegrity
      ? 'Unverified'
      : score >= 95 ? 'Grade A+' : score >= 85 ? 'Grade A' : score >= 70 ? 'Grade B' : 'Grade C';
  const unknownChecks = Object.entries(data?.security_check_details ?? {})
    .filter(([, result]) => result === 'unknown')
    .map(([name]) => name.replace(/_/g, ' '));
  const authStatus = data?.security_check_details?.auth_enforced ??
    (data?.security_checks?.auth_enforced ? 'pass' : 'fail');

  return (
    <div className="bg-linear-surface-1 border border-linear-hairline rounded-2xl overflow-hidden shadow-sm animate-fade-cascade">
      <div className="px-6 py-5 border-b border-linear-hairline bg-linear-surface-2/40 flex items-center justify-between">
        <div className="flex items-center space-x-3">
          <div className="p-2 bg-linear-success/10 rounded-lg border border-linear-success/20">
            <Shield className="w-5 h-5 text-linear-success" />
          </div>
          <div>
            <h3 className="text-base font-semibold text-linear-ink">Security & Isolation Posture</h3>
            <p className="text-xs text-linear-ink-muted mt-0.5">Automated verification of database security boundaries</p>
          </div>
        </div>
        <RefreshButton
          onRefresh={() => refetch()}
          variant="icon-dark"
          title="Re-verify posture"
        />
      </div>

      <div className="p-6 grid grid-cols-1 md:grid-cols-2 gap-8">
        {unknownChecks.length > 0 && (
          <div className="md:col-span-2 rounded-lg border border-linear-hairline bg-linear-surface-2 px-4 py-3 text-xs text-linear-ink-muted" role="status">
            <span className="font-semibold text-linear-ink">Unverified checks:</span>{' '}
            {unknownChecks.join(', ')}. These checks are not counted as passing in the score.
          </div>
        )}
        {/* Overall Score */}
        <div className="flex flex-col items-center justify-center border-b md:border-b-0 md:border-r border-linear-hairline pb-8 md:pb-0 md:pr-8">
          <div className="relative flex items-center justify-center w-40 h-40">
            <svg className="w-full h-full transform -rotate-90" viewBox="0 0 36 36">
              <path
                className="text-linear-surface-3"
                strokeWidth="3"
                stroke="currentColor"
                fill="none"
                d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831"
              />
              <path
                className={`${
                  score >= 85 ? 'text-linear-success' : score >= 70 ? 'text-amber-400' : 'text-status-warning'
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
                <Loader2 className="w-8 h-8 text-linear-ink-muted animate-fast-spin" />
              ) : (
                <>
                  <span className="text-4xl font-black text-linear-ink font-mono">{score}</span>
                  <span className="text-[10px] uppercase font-bold text-linear-ink-muted tracking-widest mt-1">
                    {grade}
                  </span>
                </>
              )}
            </div>
          </div>
          <p className="text-sm text-linear-ink-muted text-center mt-4">
            Security score computed dynamically from PostgreSQL privilege checks and cryptographic integrity.
          </p>
        </div>

        {/* Configuration Checklist */}
        <div className="flex flex-col justify-center space-y-5">
          {/* Role Isolation */}
          <div className="flex items-start space-x-3">
            <div className={`mt-0.5 w-6 h-6 rounded flex items-center justify-center flex-shrink-0 ${
              data?.security_checks?.role_isolation
                ? 'bg-linear-success/10 border border-linear-success/20 text-linear-success'
                : 'bg-status-warning/10 border border-status-warning/20 text-status-warning'
            }`}>
              {data?.security_checks?.role_isolation ? (
                <CheckCircle2 className="w-3.5 h-3.5" />
              ) : (
                <Lock className="w-3.5 h-3.5" />
              )}
            </div>
            <div>
              <p className="text-sm font-semibold text-linear-ink flex items-center gap-2">
                Role Segregation
                {data?.security_checks?.role_isolation && (
                  <span className="text-[10px] font-mono uppercase bg-linear-success/10 text-linear-success px-1.5 py-0.5 rounded border border-linear-success/20">Verified</span>
                )}
              </p>
              <p className="text-xs text-linear-ink-muted mt-0.5">
                PostgreSQL role <code className="text-linear-primary bg-linear-primary/10 border border-linear-primary/20 px-1 py-0.5 rounded">hr_admin</code> has NO direct UPDATE/DELETE privileges on <code className="text-linear-primary bg-linear-primary/10 border border-linear-primary/20 px-1 py-0.5 rounded">audit_log</code>.
              </p>
            </div>
          </div>

          {/* Authentication enforcement */}
          <div className="flex items-start justify-between gap-3 border-t border-linear-hairline pt-4">
            <div>
              <p className="text-sm font-semibold text-linear-ink">Application authentication</p>
              <p className="text-xs text-linear-ink-muted mt-0.5">
                Clerk JWT verification is configured for server-side request validation.
              </p>
            </div>
            <span className={`shrink-0 rounded border px-2 py-0.5 text-[10px] font-mono uppercase ${
              authStatus === 'pass'
                ? 'border-linear-success/30 bg-linear-success/10 text-linear-success'
                : authStatus === 'unknown'
                  ? 'border-linear-hairline bg-linear-surface-2 text-linear-ink-muted'
                  : 'border-status-warning/30 bg-status-warning/10 text-status-warning'
            }`}>
              {authStatus}
            </span>
          </div>

          {/* Cryptographic Extension */}
          <div className="flex items-start space-x-3">
            <div className={`mt-0.5 w-6 h-6 rounded flex items-center justify-center flex-shrink-0 ${
              data?.security_checks?.pgcrypto_active
                ? 'bg-linear-success/10 border border-linear-success/20 text-linear-success'
                : 'bg-status-warning/10 border border-status-warning/20 text-status-warning'
            }`}>
              {data?.security_checks?.pgcrypto_active ? (
                <CheckCircle2 className="w-3.5 h-3.5" />
              ) : (
                <Key className="w-3.5 h-3.5" />
              )}
            </div>
            <div>
              <p className="text-sm font-semibold text-linear-ink flex items-center gap-2">
                Cryptographic Extension
                {data?.security_checks?.pgcrypto_active && (
                  <span className="text-[10px] font-mono uppercase bg-linear-success/10 text-linear-success px-1.5 py-0.5 rounded border border-linear-success/20">Active</span>
                )}
              </p>
              <p className="text-xs text-linear-ink-muted mt-0.5">
                <code className="text-linear-primary bg-linear-primary/10 border border-linear-primary/20 px-1 py-0.5 rounded">pgcrypto</code> is loaded and computes HMAC-SHA256 digests in database triggers.
              </p>
            </div>
          </div>

          {/* Chain Tail Continuity */}
          <div className="flex items-start space-x-3">
            <div className={`mt-0.5 w-6 h-6 rounded flex items-center justify-center flex-shrink-0 ${
              data?.security_checks?.chain_continuous
                ? 'bg-linear-success/10 border border-linear-success/20 text-linear-success'
                : 'bg-status-warning/10 border border-status-warning/20 text-status-warning'
            }`}>
              {data?.security_checks?.chain_continuous ? (
                <CheckCircle2 className="w-3.5 h-3.5" />
              ) : (
                <XCircle className="w-3.5 h-3.5" />
              )}
            </div>
            <div>
              <p className="text-sm font-semibold text-linear-ink flex items-center gap-2">
                Chain Tail Consistency
                {data?.security_checks?.chain_continuous && (
                  <span className="text-[10px] font-mono uppercase bg-linear-success/10 text-linear-success px-1.5 py-0.5 rounded border border-linear-success/20">Tail matches</span>
                )}
              </p>
              <p className="text-xs text-linear-ink-muted mt-0.5">
                Tail checkpoint sequence matches the latest entry in <code className="text-linear-primary bg-linear-primary/10 border border-linear-primary/20 px-1 py-0.5 rounded">audit_log</code>.
              </p>
            </div>
          </div>
        </div>

      </div>
    </div>
  );
}
