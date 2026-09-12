import { useState, useEffect } from 'react';
import { useQuery } from '@tanstack/react-query';
import { useAuth } from '@clerk/clerk-react';
import {
  Play, Loader2, CheckCircle2, AlertTriangle,
  ShieldCheck, XCircle, RefreshCw,
} from 'lucide-react';
import { runVerification, type VerificationResult } from '../../services/auditService';

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
    refetchInterval: 10000,
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
    <div className="bg-slate-900/50 border border-slate-700/50 rounded-2xl overflow-hidden">
      {/* Header */}
      <div className="flex items-center justify-between px-5 py-4 border-b border-slate-700/50">
        <div className="flex items-center space-x-2.5">
          <ShieldCheck className="w-5 h-5 text-violet-400" />
          <h3 className="text-sm font-semibold text-slate-200">Chain Verification</h3>
        </div>
        {lastResult && (
          <button
            id="reverify-btn"
            onClick={() => refetch()}
            disabled={isFetching}
            className="text-xs text-slate-500 hover:text-violet-300 flex items-center space-x-1 transition-colors disabled:opacity-40"
          >
            <RefreshCw className={`w-3 h-3 ${isFetching ? 'animate-spin text-violet-400' : ''}`} />
            <span>{isFetching ? 'Verifying…' : 'Re-run'}</span>
          </button>
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
              <p className="text-sm text-slate-300 font-medium">Run Chain Verification</p>
              <p className="text-xs text-slate-600 mt-1">
                Walks the full audit hash chain and compares against the anchor store.
              </p>
            </div>
            <button
              id="run-verification-btn"
              onClick={() => refetch()}
              disabled={isFetching}
              className="inline-flex items-center px-5 py-2.5 rounded-xl text-sm font-semibold bg-violet-600 hover:bg-violet-500 text-white border border-violet-500 shadow-[0_0_20px_rgba(139,92,246,0.25)] hover:shadow-[0_0_30px_rgba(139,92,246,0.35)] transition-all duration-200 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {isFetching ? (
                <>
                  <Loader2 className="w-4 h-4 mr-2 animate-spin" />
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
          <div className="flex items-center space-x-3 px-4 py-3 rounded-xl bg-violet-500/8 border border-violet-500/15">
            <Loader2 className="w-5 h-5 text-violet-400 animate-spin flex-shrink-0" />
            <div>
              <p className="text-sm font-medium text-violet-300">Scanning hash chain…</p>
              <p className="text-xs text-slate-600 mt-0.5">Walking entries from last checkpoint</p>
            </div>
          </div>
        )}

        {/* Error state */}
        {isError && !isFetching && (
          <div className="flex items-start space-x-3 px-4 py-3 rounded-xl bg-red-500/8 border border-red-500/20">
            <XCircle className="w-5 h-5 text-red-400 flex-shrink-0 mt-0.5" />
            <div>
              <p className="text-sm font-medium text-red-300">Verification request failed</p>
              <p className="text-xs text-slate-500 mt-0.5">
                {error instanceof Error
                  ? error.message
                  : 'Network error — check the API is running.'}
              </p>
              <button
                onClick={() => refetch()}
                className="mt-2 text-xs text-red-400 hover:text-red-300 underline underline-offset-2"
              >
                Retry
              </button>
            </div>
          </div>
        )}

        {/* Result card */}
        {lastResult && (
          <div
            className={`rounded-xl border p-4 space-y-3 transition-all duration-300 ${
              isIntact
                ? 'border-emerald-500/25 bg-emerald-500/5 shadow-[0_0_20px_rgba(52,211,153,0.06)]'
                : 'border-red-500/35 bg-red-500/8 shadow-[0_0_30px_rgba(239,68,68,0.10)]'
            }`}
          >
            {/* Status headline */}
            <div className="flex items-center space-x-3">
              {isIntact ? (
                <CheckCircle2 className="w-6 h-6 text-emerald-400 drop-shadow-[0_0_6px_rgba(52,211,153,0.7)] flex-shrink-0" />
              ) : (
                <AlertTriangle className="w-6 h-6 text-red-400 drop-shadow-[0_0_8px_rgba(239,68,68,0.8)] flex-shrink-0 animate-pulse" />
              )}
              <div>
                <p className={`font-bold text-base ${isIntact ? 'text-emerald-300' : 'text-red-300'}`}>
                  {isIntact ? 'Chain Intact' : '⚠ Tampering Detected'}
                </p>
                <p className="text-xs text-slate-500 mt-0.5">{lastResult.details}</p>
              </div>
            </div>

            {/* Stats grid */}
            <div className="grid grid-cols-2 gap-2 pt-1">
              <div className="bg-slate-900/60 border border-slate-700/40 rounded-lg px-3 py-2">
                <p className="text-[10px] uppercase tracking-wider text-slate-600 font-semibold">Entries scanned</p>
                <p className="text-lg font-bold font-mono text-slate-200 mt-0.5">
                  {lastResult.entries_scanned.toLocaleString()}
                </p>
              </div>
              <div className="bg-slate-900/60 border border-slate-700/40 rounded-lg px-3 py-2">
                <p className="text-[10px] uppercase tracking-wider text-slate-600 font-semibold">Anchor match</p>
                <p className={`text-lg font-bold mt-0.5 ${lastResult.anchor_match ? 'text-emerald-400' : 'text-red-400'}`}>
                  {lastResult.anchor_match ? 'Yes' : 'No'}
                </p>
              </div>
              <div className="bg-slate-900/60 border border-slate-700/40 rounded-lg px-3 py-2">
                <p className="text-[10px] uppercase tracking-wider text-slate-600 font-semibold">Last verified ID</p>
                <p className="text-sm font-bold font-mono text-slate-300 mt-0.5">
                  #{lastResult.last_verified_sequence_id}
                </p>
              </div>
              {isTampered && lastResult.tampered_sequence_id !== null && (
                <div className="bg-red-900/20 border border-red-500/25 rounded-lg px-3 py-2">
                  <p className="text-[10px] uppercase tracking-wider text-red-600 font-semibold">Tampered at</p>
                  <p className="text-sm font-bold font-mono text-red-400 mt-0.5">
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
