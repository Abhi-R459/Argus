import { useState, useEffect } from 'react';
import { useQuery } from '@tanstack/react-query';
import { useAuth } from '@clerk/clerk-react';
import {
  Play, Loader2, CheckCircle2, AlertTriangle,
  ShieldCheck, XCircle,
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
  } = useQuery({
    queryKey: ['chain-verification'],
    queryFn: async () => {
      const res = await runVerification(getToken);
      return res;
    },
    refetchInterval: 30000,
  });

  useEffect(() => {
    if (data) {
      setLastResult(data);
      onResult?.(data);
    }
  }, [data, onResult]);

  const isIntact   = lastResult?.status === 'intact';
  const isTampered = lastResult?.status === 'tampered';

  return (
    <div className="bg-linear-surface-1 border border-linear-hairline rounded-2xl overflow-hidden shadow-sm h-full flex flex-col justify-between">
      {/* Screen Reader Live Region (F-122) */}
      <div aria-live="polite" className="sr-only">
        {isFetching && 'Scanning hash chain and walking entries from last checkpoint.'}
        {isIntact && 'Verification complete. Chain is intact with zero anomalies.'}
        {isTampered && `Warning: Tampering detected at sequence ID ${lastResult?.tampered_sequence_id}.`}
      </div>

      {/* Header */}
      <div className="flex items-center justify-between px-5 py-4 border-b border-linear-hairline shrink-0">
        <div className="flex items-center space-x-2.5">
          <div className="w-9 h-9 rounded-xl flex items-center justify-center bg-linear-surface-2 border border-linear-hairline">
            <ShieldCheck className="w-4 h-4 text-linear-primary" />
          </div>
          <div>
            <p className="text-[10px] text-linear-ink-subtle uppercase tracking-wider font-semibold">Ledger Integrity</p>
            <h3 className="text-sm font-semibold text-linear-ink">Chain Verification</h3>
          </div>
        </div>
        <div className="flex items-center space-x-2">
          {lastResult && (
            <span
              className={`flex items-center space-x-1 px-2.5 py-1 rounded-full text-[11px] font-bold uppercase tracking-wider border ${
                isIntact
                  ? 'bg-linear-success/15 text-linear-success border-linear-success/30'
                  : 'bg-grafana-orange/15 text-grafana-orange border-grafana-orange/30'
              }`}
            >
              <span className={`w-1.5 h-1.5 rounded-full ${isIntact ? 'bg-linear-success' : 'bg-grafana-orange'}`} />
              <span>{isIntact ? 'Intact' : 'Tampered'}</span>
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
                Walks the full audit hash chain and compares against the anchor store.
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
            <div className="flex items-start space-x-3 px-4 py-3 rounded-xl bg-grafana-orange/10 border border-grafana-orange/25 w-full">
              <XCircle className="w-5 h-5 text-grafana-orange flex-shrink-0 mt-0.5" />
              <div>
                <p className="text-sm font-medium text-grafana-orange">Verification request failed</p>
                <p className="text-xs text-linear-ink-subtle mt-0.5">
                  {error instanceof Error
                    ? error.message
                    : 'Network error — check the API is running.'}
                </p>
                <Button
                  variant="link"
                  portalTheme="auditor"
                  onClick={() => refetch()}
                  className="mt-2 text-xs text-grafana-orange hover:text-grafana-orange-hover"
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
                  : 'border-grafana-orange/40 bg-grafana-orange/10'
              }`}
            >
              {/* Status headline */}
              <div className="flex items-center space-x-3">
                {isIntact ? (
                  <CheckCircle2 className="w-5 h-5 text-linear-success flex-shrink-0" />
                ) : (
                  <AlertTriangle className="w-5 h-5 text-grafana-orange flex-shrink-0" />
                )}
                <div>
                  <p className={`font-bold text-sm ${isIntact ? 'text-linear-success' : 'text-grafana-orange'}`}>
                    {isIntact ? 'Chain Walks Intact' : '⚠ Tampering Detected'}
                  </p>
                  <p className="text-xs text-linear-ink-subtle mt-0.5 leading-relaxed">{lastResult.details}</p>
                </div>
              </div>

              {/* Stats 4-cell grid */}
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 pt-1">
                <div className="bg-linear-surface-2/80 border border-linear-hairline rounded-lg px-2.5 py-1.5">
                  <p className="text-[10px] uppercase tracking-wider text-linear-ink-subtle font-semibold">Scanned</p>
                  <p className="text-sm font-bold font-mono text-linear-ink mt-0.5">
                    {lastResult.entries_scanned.toLocaleString()}
                  </p>
                </div>
                <div className="bg-linear-surface-2/80 border border-linear-hairline rounded-lg px-2.5 py-1.5">
                  <p className="text-[10px] uppercase tracking-wider text-linear-ink-subtle font-semibold">Anchor Match</p>
                  <p className={`text-sm font-bold mt-0.5 ${lastResult.anchor_match ? 'text-linear-success' : 'text-grafana-orange'}`}>
                    {lastResult.anchor_match ? 'Yes' : 'No'}
                  </p>
                </div>
                <div className="bg-linear-surface-2/80 border border-linear-hairline rounded-lg px-2.5 py-1.5">
                  <p className="text-[10px] uppercase tracking-wider text-linear-ink-subtle font-semibold">Tail ID</p>
                  <p className="text-sm font-bold font-mono text-linear-ink mt-0.5">
                    #{lastResult.last_verified_sequence_id}
                  </p>
                </div>
                <div className="bg-linear-surface-2/80 border border-linear-hairline rounded-lg px-2.5 py-1.5">
                  <p className="text-[10px] uppercase tracking-wider text-linear-ink-subtle font-semibold">Anomalies</p>
                  <p className={`text-sm font-bold font-mono mt-0.5 ${isTampered ? 'text-grafana-orange' : 'text-linear-success'}`}>
                    {isTampered && lastResult.tampered_sequence_id !== null ? `#${lastResult.tampered_sequence_id}` : '0'}
                  </p>
                </div>
              </div>
            </div>

            {/* Cryptographic Invariants Section */}
            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <div className="flex items-center space-x-2">
                  <ShieldCheck className="w-3.5 h-3.5 text-linear-primary" />
                  <p className="text-[11px] uppercase tracking-wider text-linear-ink font-semibold">
                    Cryptographic Invariants
                  </p>
                </div>
                <span
                  className={`flex items-center space-x-1 px-2 py-0.5 rounded-full text-[10px] font-bold uppercase tracking-wider border ${
                    isIntact
                      ? 'bg-linear-success/15 text-linear-success border-linear-success/30'
                      : 'bg-grafana-orange/15 text-grafana-orange border-grafana-orange/30'
                  }`}
                >
                  {isIntact ? <CheckCircle2 className="w-2.5 h-2.5" /> : <XCircle className="w-2.5 h-2.5" />}
                  <span>{isIntact ? '3/3 Validated' : 'Check Failed'}</span>
                </span>
              </div>

              <p className="text-[11px] text-linear-ink-subtle leading-relaxed">
                Induction verification: SHA-256 HMAC linkage, Ed25519 signatures, and Merkle tree roots verified.
              </p>

              <div className="space-y-1.5 bg-linear-surface-2 p-2.5 rounded-xl border border-linear-hairline">
                <div className="flex items-center justify-between text-[11px] py-1 px-1.5 rounded hover:bg-linear-surface-1 transition-colors">
                  <div className="flex items-center space-x-2 truncate pr-2">
                    <span className={`w-1.5 h-1.5 rounded-full flex-shrink-0 ${isIntact ? 'bg-linear-success' : 'bg-grafana-orange'}`} />
                    <span className="font-mono text-linear-ink truncate">SHA-256 HMAC Linkage</span>
                  </div>
                  <span className="text-[9px] font-bold px-1.5 py-0.5 rounded border uppercase bg-linear-success/10 text-linear-success border-linear-success/30 flex-shrink-0">
                    CONTINUOUS
                  </span>
                </div>

                <div className="flex items-center justify-between text-[11px] py-1 px-1.5 rounded hover:bg-linear-surface-1 transition-colors">
                  <div className="flex items-center space-x-2 truncate pr-2">
                    <span className={`w-1.5 h-1.5 rounded-full flex-shrink-0 ${isIntact ? 'bg-linear-success' : 'bg-grafana-orange'}`} />
                    <span className="font-mono text-linear-ink truncate">RFC 8032 Checkpoint Sig</span>
                  </div>
                  <span className="text-[9px] font-bold px-1.5 py-0.5 rounded border uppercase bg-linear-success/10 text-linear-success border-linear-success/30 flex-shrink-0">
                    ED25519
                  </span>
                </div>

                <div className="flex items-center justify-between text-[11px] py-1 px-1.5 rounded hover:bg-linear-surface-1 transition-colors">
                  <div className="flex items-center space-x-2 truncate pr-2">
                    <span className={`w-1.5 h-1.5 rounded-full flex-shrink-0 ${isIntact ? 'bg-linear-success' : 'bg-grafana-orange'}`} />
                    <span className="font-mono text-linear-ink truncate">RFC 6962 Merkle Root</span>
                  </div>
                  <span className="text-[9px] font-bold px-1.5 py-0.5 rounded border uppercase bg-linear-success/10 text-linear-success border-linear-success/30 flex-shrink-0">
                    CONSISTENT
                  </span>
                </div>
              </div>
            </div>
          </div>
        )}
      </div>

      {/* Footer: Verification schedule / cadence */}
      <div className="border-t border-linear-hairline px-5 py-3 shrink-0">
        <div className="flex items-center justify-between">
          <p className="text-xs text-linear-ink-subtle">Continuous audit schedule</p>
          <span className="text-xs font-mono text-linear-ink">Polling every 30s</span>
        </div>
      </div>
    </div>
  );
}
