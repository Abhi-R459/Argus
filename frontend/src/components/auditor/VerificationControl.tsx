import { useState, useEffect } from 'react';
import { useQuery } from '@tanstack/react-query';
import { useAuth } from '@clerk/clerk-react';
import {
  Play, Loader2, CheckCircle2, AlertTriangle,
  ShieldCheck, XCircle, HelpCircle,
} from 'lucide-react';
import { runVerification, type VerificationResult } from '../../services/auditService';
import RefreshButton from '../common/RefreshButton';
import { Button } from '../common/Button';

interface VerificationControlProps {
  onResult?: (result: VerificationResult) => void;
}

export default function VerificationControl({ onResult }: VerificationControlProps = {}) {
  const { getToken } = useAuth();
  const [lastResult, setLastResult] = useState<VerificationResult | null>(null);

  const {
    data,
    isError,
    error,
    refetch,
    isFetching,
    dataUpdatedAt,
  } = useQuery({
    queryKey: ['chain-verification'],
    enabled: false,
    queryFn: async () => {
      const res = await runVerification(getToken);
      return res;
    },
  });

  useEffect(() => {
    if (data) {
      setLastResult(data);
      onResult?.(data);
    }
  }, [data, onResult]);

  const isIntact   = lastResult?.status === 'intact';
  const isTampered = lastResult?.status === 'tampered';
  const isUnverified = lastResult?.status === 'unknown' || lastResult?.status === 'error';
  const checkStatus = (name: string): 'pass' | 'fail' | 'unknown' => {
    const reported = lastResult?.verification_checks?.[name];
    if (reported) return reported;
    if (name === 'hash_chain' && isIntact) return 'pass';
    if (name === 'hash_chain' && isTampered) return 'fail';
    return 'unknown';
  };
  const checkRows = [
    { key: 'hash_chain', label: 'Audit hash chain' },
    { key: 'external_anchor', label: 'Configured anchor record comparison' },
    { key: 'checkpoint_signatures', label: 'Checkpoint signatures' },
  ];
  const verifiedCheckCount = checkRows.filter((check) => checkStatus(check.key) === 'pass').length;

  return (
    <div className="bg-linear-surface-1 border border-linear-hairline rounded-2xl overflow-hidden shadow-sm flex flex-col justify-between">
      {/* Screen Reader Live Region (F-122) */}
      <div aria-live="polite" className="sr-only">
        {isFetching && 'Scanning hash chain and walking entries from last checkpoint.'}
        {isIntact && `Last check passed through sequence ${lastResult?.last_verified_sequence_id}.`}
        {isTampered && `Warning: Tampering detected at sequence ID ${lastResult?.tampered_sequence_id}.`}
      </div>

      {/* Header */}
      <div className="flex items-center justify-between px-5 py-4 border-b border-linear-hairline shrink-0">
        <div className="flex items-center space-x-2.5">
          <div className="w-9 h-9 rounded-xl flex items-center justify-center bg-linear-surface-2 border border-linear-hairline">
            <ShieldCheck className="w-4 h-4 text-linear-primary" />
          </div>
          <div>
            <p className="text-xs text-linear-ink-subtle font-medium">Ledger integrity</p>
            <h3 className="text-base font-semibold text-linear-ink">Chain verification</h3>
          </div>
        </div>
        <div className="flex items-center space-x-2">
          {lastResult && (
            <span
              className={`flex items-center space-x-1 px-2.5 py-1 rounded-full text-[11px] font-bold uppercase tracking-wider border ${
                isIntact
                  ? 'bg-linear-success/15 text-linear-success border-linear-success/30'
                  : isUnverified
                    ? 'bg-linear-surface-2 text-linear-ink-muted border-linear-hairline'
                    : 'bg-status-warning/15 text-status-warning border-status-warning/30'
              }`}
            >
              <span className={`w-1.5 h-1.5 rounded-full ${isIntact ? 'bg-linear-success' : isUnverified ? 'bg-linear-ink-muted' : 'bg-status-warning'}`} />
              <span>{isIntact ? 'Last check passed' : isTampered ? 'Tampered' : lastResult?.status === 'error' ? 'Unavailable' : 'Unverified'}</span>
            </span>
          )}
          {lastResult && (
            <RefreshButton
              onRefresh={() => refetch()}
              label="Re-run"
              variant="dark"
              title="Re-run chain verification"
              size="sm"
              className="text-xs px-2 py-1"
            />
          )}
        </div>
      </div>

      <div className="p-5 flex-1 flex flex-col justify-between space-y-3.5">
        {/* Trigger button — shown when no result yet */}
        {!lastResult && !isFetching && !isError && (
          <div className="flex-1 flex flex-col items-center justify-center py-6 space-y-4">
            <div className="w-14 h-14 rounded-2xl bg-linear-primary/10 border border-linear-primary/20 flex items-center justify-center">
              <ShieldCheck className="w-7 h-7 text-linear-primary" />
            </div>
            <div className="text-center">
              <p className="text-sm text-linear-ink font-medium">Run Chain Verification</p>
              <p className="text-xs text-linear-ink-subtle mt-1 max-w-xs">
                Walks the full audit hash chain and checks the latest local anchor record.
              </p>
            </div>
            <Button
              id="verification-control-run-btn"
              variant="primary"
              size="md"
              portalTheme="auditor"
              onClick={() => refetch()}
              disabled={isFetching}
              loading={isFetching}
              leftIcon={<Play className="w-3.5 h-3.5" />}
            >
              Run Verification
            </Button>
          </div>
        )}

        {/* Running state overlay */}
        {isFetching && !lastResult && (
          <div className="flex-1 flex items-center justify-center">
            <div className="flex items-center space-x-3 px-4 py-3 rounded-xl bg-linear-primary/10 border border-linear-primary/20 w-full max-w-sm">
              <Loader2 className="w-5 h-5 text-linear-primary animate-fast-spin flex-shrink-0" />
              <div>
                <p className="text-sm font-medium text-linear-primary">Scanning hash chain…</p>
                <p className="text-xs text-linear-ink-subtle mt-0.5">Walking entries from last checkpoint</p>
              </div>
            </div>
          </div>
        )}

        {/* Error state */}
        {isError && !isFetching && (
          <div className="flex-1 flex items-center justify-center">
            <div className="flex items-start space-x-3 px-4 py-3 rounded-xl bg-status-warning/10 border border-status-warning/25 w-full">
              <XCircle className="w-5 h-5 text-status-warning flex-shrink-0 mt-0.5" />
              <div>
                <p className="text-sm font-medium text-status-warning">Verification request failed</p>
                <p className="text-xs text-linear-ink-subtle mt-0.5">
                  {error instanceof Error
                    ? error.message
                    : 'Network error — check the API is running.'}
                </p>
                <Button
                  variant="link"
                  portalTheme="auditor"
                  onClick={() => refetch()}
                  className="mt-2 text-xs text-status-warning hover:text-status-warning-hover"
                >
                  Retry
                </Button>
              </div>
            </div>
          </div>
        )}

        {/* Result card */}
        {lastResult && (
          <div className="space-y-3.5 flex-1 flex flex-col justify-between">
            <div
              className={`rounded-xl border p-3.5 space-y-2.5 transition-[border-color,background-color] duration-200 shadow-xs ${
                isIntact
                  ? 'border-linear-success/30 bg-linear-success/10'
                  : isUnverified
                    ? 'border-linear-hairline bg-linear-surface-2/60'
                    : 'border-status-warning/40 bg-status-warning/10'
              }`}
            >
              {/* Status headline */}
              <div className="flex items-center space-x-3">
                {isIntact ? (
                  <CheckCircle2 className="w-5 h-5 text-linear-success flex-shrink-0" />
                ) : isUnverified ? (
                  <HelpCircle className="w-5 h-5 text-linear-ink-muted flex-shrink-0" />
                ) : (
                  <AlertTriangle className="w-5 h-5 text-status-warning flex-shrink-0" />
                )}
                <div>
                  <p className={`font-bold text-sm ${isIntact ? 'text-linear-success' : isUnverified ? 'text-linear-ink' : 'text-status-warning'}`}>
                    {isIntact ? 'Last check passed' : isTampered ? 'Tampering Detected' : lastResult?.status === 'error' ? 'Verification Unavailable' : 'Verification Incomplete'}
                  </p>
                  <p className="text-xs text-linear-ink-subtle mt-0.5 leading-relaxed">{lastResult.details}</p>
                  <p className="text-[11px] text-linear-ink-muted mt-1">
                    Checked through sequence #{lastResult.last_verified_sequence_id}
                    {dataUpdatedAt ? ` · ${new Date(dataUpdatedAt).toLocaleString()}` : ''}. Run again to check newer events.
                  </p>
                </div>
              </div>

              {/* Stats 4-cell grid */}
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 pt-1">
                <div className="bg-linear-surface-2/80 border border-linear-hairline rounded-lg px-2.5 py-1.5">
                  <p className="text-xs text-linear-ink-subtle font-medium">Scanned</p>
                  <p className="text-sm font-bold font-mono text-linear-ink mt-0.5">
                    {lastResult.entries_scanned.toLocaleString()}
                  </p>
                </div>
                <div className="bg-linear-surface-2/80 border border-linear-hairline rounded-lg px-2.5 py-1.5">
                  <p className="text-xs text-linear-ink-subtle font-medium">Configured anchor record</p>
                  <p className={`text-sm font-bold mt-0.5 ${checkStatus('external_anchor') === 'pass' ? 'text-linear-success' : checkStatus('external_anchor') === 'unknown' ? 'text-linear-ink-muted' : 'text-status-warning'}`}>
                    {checkStatus('external_anchor') === 'pass' ? 'Verified' : checkStatus('external_anchor') === 'fail' ? 'Mismatch' : 'Unverified'}
                  </p>
                </div>
                <div className="bg-linear-surface-2/80 border border-linear-hairline rounded-lg px-2.5 py-1.5">
                  <p className="text-xs text-linear-ink-subtle font-medium">Tail ID</p>
                  <p className="text-sm font-bold font-mono text-linear-ink mt-0.5">
                    #{lastResult.last_verified_sequence_id}
                  </p>
                </div>
                <div className="bg-linear-surface-2/80 border border-linear-hairline rounded-lg px-2.5 py-1.5">
                  <p className="text-xs text-linear-ink-subtle font-medium">Anomalies</p>
                  <p className={`text-sm font-bold font-mono mt-0.5 ${isTampered ? 'text-status-warning' : isIntact ? 'text-linear-success' : 'text-linear-ink-muted'}`}>
                    {isTampered && lastResult.tampered_sequence_id !== null ? `#${lastResult.tampered_sequence_id}` : isIntact ? '0' : '—'}
                  </p>
                </div>
              </div>
            </div>

            {/* Only backend-reported checks are presented as verified. */}
            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <div className="flex items-center space-x-2">
                  <ShieldCheck className="w-3.5 h-3.5 text-linear-primary" />
                  <p className="text-xs text-linear-ink font-semibold">
                    Checks reported by verifier
                  </p>
                </div>
                <span
                  className={`flex items-center space-x-1 px-2 py-0.5 rounded-full text-[10px] font-bold uppercase tracking-wider border ${
                    verifiedCheckCount === checkRows.length
                      ? 'bg-linear-success/15 text-linear-success border-linear-success/30'
                      : 'bg-linear-surface-2 text-linear-ink-muted border-linear-hairline'
                  }`}
                >
                  {verifiedCheckCount === checkRows.length ? <CheckCircle2 className="w-2.5 h-2.5" /> : <HelpCircle className="w-2.5 h-2.5" />}
                  <span>{verifiedCheckCount}/{checkRows.length} verified</span>
                </span>
              </div>

              <p className="text-[11px] text-linear-ink-subtle leading-relaxed">
                This result covers the hash-chain walk, the configured anchor record, and signed checkpoints. A local file anchor is not an independent external trust domain. Merkle proofs are verified separately when generated.
              </p>

              <div className="space-y-1.5 bg-linear-surface-2 p-2.5 rounded-xl border border-linear-hairline">
                {checkRows.map((check) => {
                  const status = checkStatus(check.key);
                  const statusClass = status === 'pass'
                    ? 'text-linear-success'
                    : status === 'fail' ? 'text-status-warning' : 'text-linear-ink-muted';
                  return (
                    <div key={check.key} className="flex items-center justify-between text-[11px] py-1 px-1.5 rounded hover:bg-linear-surface-1 transition-colors">
                      <div className="flex items-center space-x-2 truncate pr-2">
                        <span className={`w-1.5 h-1.5 rounded-full flex-shrink-0 ${status === 'pass' ? 'bg-linear-success' : status === 'fail' ? 'bg-status-warning' : 'bg-linear-ink-muted'}`} />
                        <span className="font-mono text-linear-ink truncate">{check.label}</span>
                      </div>
                      <span className={`text-[9px] font-bold px-1.5 py-0.5 rounded border uppercase border-current/30 bg-current/10 flex-shrink-0 ${statusClass}`}>
                        {status === 'pass' ? 'Verified' : status === 'fail' ? 'Failed' : 'Unverified'}
                      </span>
                    </div>
                  );
                })}
              </div>
            </div>
          </div>
        )}
      </div>

      {/* Footer: Verification runs on demand */}
      <div className="border-t border-linear-hairline px-5 py-3 shrink-0">
        <div className="flex items-center justify-between">
          <p className="text-xs text-linear-ink-subtle">Integrity verification</p>
          <span className="text-xs font-mono text-linear-ink">Runs on demand</span>
        </div>
      </div>
    </div>
  );
}
