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
    <div className="bg-linear-surface-1 border border-linear-hairline rounded-2xl overflow-hidden shadow-sm">
      {/* Screen Reader Live Region (F-122) */}
      <div aria-live="polite" className="sr-only">
        {isFetching && 'Scanning hash chain and walking entries from last checkpoint.'}
        {isIntact && 'Verification complete. Chain is intact with zero anomalies.'}
        {isTampered && `Warning: Tampering detected at sequence ID ${lastResult?.tampered_sequence_id}.`}
      </div>

      {/* Header */}
      <div className="flex items-center justify-between px-5 py-4 border-b border-linear-hairline">
        <div className="flex items-center space-x-2.5">
          <ShieldCheck className="w-5 h-5 text-linear-primary" />
          <h3 className="text-sm font-semibold text-linear-ink">Chain Verification</h3>
        </div>
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

      <div className="p-5 space-y-4">
        {/* Trigger button — shown when no result yet */}
        {!lastResult && (
          <div className="flex flex-col items-center justify-center py-6 space-y-4">
            <div className="w-14 h-14 rounded-2xl bg-linear-primary/10 border border-linear-primary/20 flex items-center justify-center">
              <ShieldCheck className="w-7 h-7 text-linear-primary" />
            </div>
            <div className="text-center">
              <p className="text-sm text-linear-ink font-medium">Run Chain Verification</p>
              <p className="text-xs text-linear-ink-subtle mt-1">
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
          <div className="flex items-center space-x-3 px-4 py-3 rounded-xl bg-linear-primary/10 border border-linear-primary/20">
            <Loader2 className="w-5 h-5 text-linear-primary animate-fast-spin flex-shrink-0" />
            <div>
              <p className="text-sm font-medium text-linear-primary">Scanning hash chain…</p>
              <p className="text-xs text-linear-ink-subtle mt-0.5">Walking entries from last checkpoint</p>
            </div>
          </div>
        )}

        {/* Error state */}
        {isError && !isFetching && (
          <div className="flex items-start space-x-3 px-4 py-3 rounded-xl bg-grafana-orange/10 border border-grafana-orange/25">
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
        )}

        {/* Result card */}
        {lastResult && (
          <div
            className={`rounded-xl border p-4 space-y-3 transition-[border-color,background-color] duration-200 shadow-xs ${
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
                <p className={`font-bold text-base ${isIntact ? 'text-linear-success' : 'text-grafana-orange'}`}>
                  {isIntact ? 'Chain Intact' : '⚠ Tampering Detected'}
                </p>
                <p className="text-xs text-linear-ink-subtle mt-0.5">{lastResult.details}</p>
              </div>
            </div>

            {/* Stats grid */}
            <div className="grid grid-cols-2 gap-2 pt-1">
              <div className="bg-linear-surface-2 border border-linear-hairline rounded-lg px-3 py-2">
                <p className="text-[10px] uppercase tracking-wider text-linear-ink-subtle font-semibold">Entries scanned</p>
                <p className="text-lg font-bold font-mono text-linear-ink mt-0.5">
                  {lastResult.entries_scanned.toLocaleString()}
                </p>
              </div>
              <div className="bg-linear-surface-2 border border-linear-hairline rounded-lg px-3 py-2">
                <p className="text-[10px] uppercase tracking-wider text-linear-ink-subtle font-semibold">Anchor match</p>
                <p className={`text-lg font-bold mt-0.5 ${lastResult.anchor_match ? 'text-linear-success' : 'text-grafana-orange'}`}>
                  {lastResult.anchor_match ? 'Yes' : 'No'}
                </p>
              </div>
              <div className="bg-linear-surface-2 border border-linear-hairline rounded-lg px-3 py-2">
                <p className="text-[10px] uppercase tracking-wider text-linear-ink-subtle font-semibold">Last verified ID</p>
                <p className="text-sm font-bold font-mono text-linear-ink mt-0.5">
                  #{lastResult.last_verified_sequence_id}
                </p>
              </div>
              {isTampered && lastResult.tampered_sequence_id !== null && (
                <div className="bg-grafana-orange/20 border border-grafana-orange/35 rounded-lg px-3 py-2">
                  <p className="text-[10px] uppercase tracking-wider text-grafana-orange font-semibold">Tampered at</p>
                  <p className="text-sm font-bold font-mono text-white mt-0.5">
                    #{lastResult.tampered_sequence_id}
                  </p>
                </div>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
