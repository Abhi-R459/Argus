import { useState } from 'react';
import { CheckCircle2, AlertTriangle, Loader2, Play, RefreshCw } from 'lucide-react';
import type { VerificationBannerResult as VerificationResult } from '../../services/auditService';

interface StatusBannerProps {
  data: VerificationResult;
  onRunVerification?: () => void;
}

function formatRelativeTime(isoString: string): string {
  const diff = Date.now() - new Date(isoString).getTime();
  const minutes = Math.floor(diff / 60000);
  if (minutes < 1) return 'just now';
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  return `${Math.floor(hours / 24)}d ago`;
}

function truncateHash(hash: string, chars = 12): string {
  return `${hash.slice(0, chars)}…`;
}

export default function StatusBanner({ data, onRunVerification }: StatusBannerProps) {
  const [isRunning, setIsRunning] = useState(false);

  const handleRun = async () => {
    setIsRunning(true);
    // Simulate async call; real swap will call POST /api/verify
    await new Promise((r) => setTimeout(r, 1800));
    setIsRunning(false);
    onRunVerification?.();
  };

  const isVerified = data.status === 'VERIFIED';
  const isTampered = data.status === 'TAMPERED';
  const isPending = data.status === 'PENDING';

  return (
    <div
      className={`relative rounded-2xl border overflow-hidden transition-all duration-500 ${
        isVerified
          ? 'border-emerald-500/30 bg-emerald-500/5 shadow-[0_0_40px_rgba(52,211,153,0.08)]'
          : isTampered
          ? 'border-red-500/40 bg-red-500/8 shadow-[0_0_50px_rgba(239,68,68,0.15)] animate-pulse'
          : 'border-amber-500/30 bg-amber-500/5 shadow-[0_0_30px_rgba(245,158,11,0.08)]'
      }`}
    >
      {/* Background gradient overlay */}
      <div
        className={`absolute inset-0 opacity-30 pointer-events-none ${
          isVerified
            ? 'bg-gradient-to-r from-emerald-950/50 to-transparent'
            : isTampered
            ? 'bg-gradient-to-r from-red-950/60 to-transparent'
            : 'bg-gradient-to-r from-amber-950/50 to-transparent'
        }`}
      />

      <div className="relative p-6">
        <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4">
          {/* Left: status icon + headline */}
          <div className="flex items-start space-x-4">
            <div
              className={`flex-shrink-0 w-12 h-12 rounded-xl flex items-center justify-center ${
                isVerified
                  ? 'bg-emerald-500/15 border border-emerald-500/25'
                  : isTampered
                  ? 'bg-red-500/20 border border-red-500/35'
                  : 'bg-amber-500/15 border border-amber-500/25'
              }`}
            >
              {isVerified && (
                <CheckCircle2 className="w-6 h-6 text-emerald-400 drop-shadow-[0_0_8px_rgba(52,211,153,0.8)]" />
              )}
              {isTampered && (
                <AlertTriangle className="w-6 h-6 text-red-400 drop-shadow-[0_0_10px_rgba(239,68,68,0.9)] animate-bounce" />
              )}
              {isPending && (
                <Loader2 className="w-6 h-6 text-amber-400 animate-spin" />
              )}
            </div>

            <div>
              <div className="flex items-center space-x-2">
                <h2
                  className={`text-xl font-bold tracking-tight ${
                    isVerified ? 'text-emerald-300' : isTampered ? 'text-red-300' : 'text-amber-300'
                  }`}
                >
                  {isVerified && 'Chain Integrity: Verified'}
                  {isTampered && '⚠ Tampering Detected — Immediate Action Required'}
                  {isPending && 'Verification Pending…'}
                </h2>
                <span
                  className={`text-[10px] uppercase font-bold tracking-widest px-2 py-0.5 rounded-full border ${
                    isVerified
                      ? 'text-emerald-400 border-emerald-500/30 bg-emerald-500/10'
                      : isTampered
                      ? 'text-red-400 border-red-500/40 bg-red-500/15'
                      : 'text-amber-400 border-amber-500/30 bg-amber-500/10'
                  }`}
                >
                  {data.status}
                </span>
              </div>
              <p className="text-sm text-slate-400 mt-1">
                {isVerified &&
                  `All ${data.checked_entries.toLocaleString()} entries verified in ${data.duration_ms}ms · Last checkpoint #${data.last_checkpoint_id}`}
                {isTampered &&
                  `Hash chain broken · ${data.error_detail || 'Entry hash mismatch detected'}`}
                {isPending && 'Awaiting verification run…'}
              </p>

              {/* Metadata row */}
              <div className="flex flex-wrap items-center gap-x-4 gap-y-1 mt-3">
                <span className="text-xs text-slate-500 font-mono">
                  Last run: <span className="text-slate-300">{formatRelativeTime(data.last_run)}</span>
                </span>
                <span className="text-xs text-slate-500 font-mono hidden md:inline">
                  Checkpoint hash:{' '}
                  <span className="text-slate-300">{truncateHash(data.last_checkpoint_hash)}</span>
                </span>
              </div>
            </div>
          </div>

          {/* Right: action button */}
          <div className="flex-shrink-0 flex items-center space-x-2">
            <button
              id="run-verification-btn"
              onClick={handleRun}
              disabled={isRunning}
              className={`inline-flex items-center px-4 py-2.5 rounded-xl text-sm font-semibold border transition-all duration-200 disabled:opacity-60 disabled:cursor-not-allowed ${
                isVerified
                  ? 'text-emerald-300 border-emerald-500/30 bg-emerald-500/10 hover:bg-emerald-500/20 hover:border-emerald-500/50'
                  : isTampered
                  ? 'text-red-300 border-red-500/40 bg-red-500/15 hover:bg-red-500/25'
                  : 'text-amber-300 border-amber-500/30 bg-amber-500/10 hover:bg-amber-500/20'
              }`}
            >
              {isRunning ? (
                <>
                  <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                  Verifying…
                </>
              ) : (
                <>
                  {isVerified ? (
                    <RefreshCw className="w-4 h-4 mr-2" />
                  ) : (
                    <Play className="w-4 h-4 mr-2" />
                  )}
                  Run Verification
                </>
              )}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
