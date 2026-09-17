import { useState, useEffect } from 'react';
import { useQuery } from '@tanstack/react-query';
import { useAuth } from '@clerk/clerk-react';
import {
  Play, Loader2, CheckCircle2, AlertTriangle,
  ShieldCheck, XCircle,
} from 'lucide-react';
import { runVerification, type VerificationResult } from '../../services/auditService';
import RefreshButton from '../common/RefreshButton';

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
    refetchInterval: 3000,
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
    <div className="bg-[#0F172A]/80 border border-slate-800/80 rounded-2xl overflow-hidden shadow-sm">
      {/* Header */}
      <div className="flex items-center justify-between px-5 py-4 border-b border-slate-800/80">
        <div className="flex items-center space-x-2.5">
          <ShieldCheck className="w-5 h-5 text-violet-400" />
          <h3 className="text-sm font-semibold text-slate-100">Chain Verification</h3>
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
            <div className="w-14 h-14 rounded-2xl bg-violet-500/10 border border-violet-500/20 flex items-center justify-center">
              <ShieldCheck className="w-7 h-7 text-violet-400" />
            </div>
            <div className="text-center">
              <p className="text-sm text-slate-200 font-medium">Run Chain Verification</p>
              <p className="text-xs text-slate-400 mt-1">
                Walks the full audit hash chain and compares against the anchor store.
              </p>
            </div>
            <button
              id="run-verification-btn"
              onClick={() => refetch()}
              disabled={isFetching}
              className="btn-press inline-flex items-center px-5 py-2.5 rounded-xl text-sm font-semibold bg-violet-600 hover:bg-violet-500 text-white border border-violet-500 shadow-[0_0_16px_rgba(139,92,246,0.3)] transition-colors duration-150 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {isFetching ? (
                <>
                  <Loader2 className="w-4 h-4 mr-2 animate-fast-spin" />
                  Verifying chain…
                </>
              ) : (
                <>
                  <Play className="w-4 h-4 mr-2" />
                  Run Verification
                </>
              )}
            </button>
          </div>
        )}

        {/* Running state overlay */}
        {isFetching && !lastResult && (
          <div className="flex items-center space-x-3 px-4 py-3 rounded-xl bg-violet-500/10 border border-violet-500/20">
            <Loader2 className="w-5 h-5 text-violet-400 animate-fast-spin flex-shrink-0" />
            <div>
              <p className="text-sm font-medium text-violet-200">Scanning hash chain…</p>
              <p className="text-xs text-slate-400 mt-0.5">Walking entries from last checkpoint</p>
            </div>
          </div>
        )}

        {/* Error state */}
        {isError && !isFetching && (
          <div className="flex items-start space-x-3 px-4 py-3 rounded-xl bg-rose-500/10 border border-rose-500/25">
            <XCircle className="w-5 h-5 text-rose-400 flex-shrink-0 mt-0.5" />
            <div>
              <p className="text-sm font-medium text-rose-300">Verification request failed</p>
              <p className="text-xs text-slate-400 mt-0.5">
                {error instanceof Error
                  ? error.message
                  : 'Network error — check the API is running.'}
              </p>
              <button
                onClick={() => refetch()}
                className="btn-press-sm mt-2 text-xs text-rose-400 hover:text-rose-300 underline underline-offset-2"
              >
                Retry
              </button>
            </div>
          </div>
        )}

        {/* Result card */}
        {lastResult && (
          <div
            className={`rounded-xl border p-4 space-y-3 transition-[border-color,background-color] duration-200 ${
              isIntact
                ? 'border-emerald-500/30 bg-emerald-500/10 shadow-[0_0_20px_rgba(52,211,153,0.08)]'
                : 'border-rose-500/40 bg-rose-500/10 shadow-[0_0_30px_rgba(244,63,94,0.12)]'
            }`}
          >
            {/* Status headline */}
            <div className="flex items-center space-x-3">
              {isIntact ? (
                <CheckCircle2 className="w-6 h-6 text-emerald-400 drop-shadow-[0_0_8px_rgba(52,211,153,0.8)] flex-shrink-0" />
              ) : (
                <AlertTriangle className="w-6 h-6 text-rose-400 drop-shadow-[0_0_8px_rgba(244,63,94,0.9)] flex-shrink-0 animate-pulse" />
              )}
              <div>
                <p className={`font-bold text-base ${isIntact ? 'text-emerald-300' : 'text-rose-300'}`}>
                  {isIntact ? 'Chain Intact' : '⚠ Tampering Detected'}
                </p>
                <p className="text-xs text-slate-400 mt-0.5">{lastResult.details}</p>
              </div>
            </div>

            {/* Stats grid */}
            <div className="grid grid-cols-2 gap-2 pt-1">
              <div className="bg-[#0B0F17]/70 border border-slate-800/80 rounded-lg px-3 py-2">
                <p className="text-[10px] uppercase tracking-wider text-slate-400 font-semibold">Entries scanned</p>
                <p className="text-lg font-bold font-mono text-slate-100 mt-0.5">
                  {lastResult.entries_scanned.toLocaleString()}
                </p>
              </div>
              <div className="bg-[#0B0F17]/70 border border-slate-800/80 rounded-lg px-3 py-2">
                <p className="text-[10px] uppercase tracking-wider text-slate-400 font-semibold">Anchor match</p>
                <p className={`text-lg font-bold mt-0.5 ${lastResult.anchor_match ? 'text-emerald-400' : 'text-rose-400'}`}>
                  {lastResult.anchor_match ? 'Yes' : 'No'}
                </p>
              </div>
              <div className="bg-[#0B0F17]/70 border border-slate-800/80 rounded-lg px-3 py-2">
                <p className="text-[10px] uppercase tracking-wider text-slate-400 font-semibold">Last verified ID</p>
                <p className="text-sm font-bold font-mono text-slate-200 mt-0.5">
                  #{lastResult.last_verified_sequence_id}
                </p>
              </div>
              {isTampered && lastResult.tampered_sequence_id !== null && (
                <div className="bg-rose-950/40 border border-rose-500/30 rounded-lg px-3 py-2">
                  <p className="text-[10px] uppercase tracking-wider text-rose-400 font-semibold">Tampered at</p>
                  <p className="text-sm font-bold font-mono text-rose-300 mt-0.5">
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
