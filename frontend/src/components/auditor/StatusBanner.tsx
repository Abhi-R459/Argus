import { useState } from 'react';
import { CheckCircle2, AlertTriangle, Loader2, Play, RefreshCw } from 'lucide-react';
import { Button } from '../common/Button';
import type { VerificationBannerResult as VerificationResult } from '../../services/auditService';

interface StatusBannerProps {
  data: VerificationResult;
  onRunVerification?: () => void;
}

function formatRelativeTime(isoString: string): string {
  const diff = Math.max(0, Date.now() - new Date(isoString).getTime());
  const seconds = Math.floor(diff / 1000);
  if (seconds < 5) return 'just now';
  if (seconds < 60) return `${seconds}s ago`;
  const minutes = Math.floor(seconds / 60);
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
      className={`relative rounded-xl border overflow-hidden transition-all duration-300 ${
        isVerified
          ? 'border-linear-success/30 bg-linear-success/5 shadow-xs'
          : isTampered
          ? 'border-grafana-orange/40 bg-grafana-orange/10 shadow-xs'
          : 'border-linear-hairline bg-linear-surface-1 shadow-xs'
      }`}
    >
      {/* Subtle tint */}
      <div
        className={`absolute inset-0 opacity-20 pointer-events-none ${
          isVerified
            ? 'bg-linear-success/10'
            : isTampered
            ? 'bg-grafana-orange/15'
            : 'bg-transparent'
        }`}
      />

      <div className="relative p-6">
        <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4">
          {/* Left: status icon + headline */}
          <div className="flex items-start space-x-4">
            <div
              className={`flex-shrink-0 w-11 h-11 rounded-xl flex items-center justify-center ${
                isVerified
                  ? 'bg-linear-success/15 border border-linear-success/25'
                  : isTampered
                  ? 'bg-grafana-orange/20 border border-grafana-orange/35'
                  : 'bg-linear-surface-2 border border-linear-hairline'
              }`}
            >
              {isVerified && (
                <CheckCircle2 className="w-5 h-5 text-linear-success" />
              )}
              {isTampered && (
                <AlertTriangle className="w-5 h-5 text-grafana-orange" />
              )}
              {isPending && (
                <Loader2 className="w-5 h-5 text-linear-primary animate-spin" />
              )}
            </div>

            <div>
              <div className="flex items-center space-x-2">
                <h2
                  className={`text-xl font-bold tracking-tight ${
                    isVerified ? 'text-linear-success' : isTampered ? 'text-grafana-orange' : 'text-linear-ink'
                  }`}
                >
                  {isVerified && 'Chain Integrity: Verified'}
                  {isTampered && '⚠ Tampering Detected — Immediate Action Required'}
                  {isPending && 'Verification Pending…'}
                </h2>
                <span
                  className={`text-[10px] uppercase font-bold tracking-widest px-2 py-0.5 rounded-full border ${
                    isVerified
                      ? 'text-linear-success border-linear-success/30 bg-linear-success/10'
                      : isTampered
                      ? 'text-white border-grafana-orange/50 bg-grafana-orange'
                      : 'text-linear-ink-subtle border-linear-hairline bg-linear-surface-2'
                  }`}
                >
                  {data.status}
                </span>
              </div>
              <p className="text-sm text-linear-ink-subtle mt-1">
                {isVerified &&
                  `All ${data.checked_entries.toLocaleString()} entries verified in ${data.duration_ms}ms · Last checkpoint #${data.last_checkpoint_id}`}
                {isTampered &&
                  `Hash chain broken · ${data.error_detail || 'Entry hash mismatch detected'}`}
                {isPending && 'Awaiting verification run…'}
              </p>

              {/* Metadata row */}
              <div className="flex flex-wrap items-center gap-x-4 gap-y-1 mt-3">
                <span className="text-xs text-linear-ink-subtle font-mono">
                  Last run: <span className="text-linear-ink-muted">{formatRelativeTime(data.last_run)}</span>
                </span>
                <span className="text-xs text-linear-ink-subtle font-mono hidden md:inline">
                  Checkpoint hash:{' '}
                  <span className="text-linear-ink-muted">{truncateHash(data.last_checkpoint_hash)}</span>
                </span>
              </div>
            </div>
          </div>

          {/* Right: action button */}
          <div className="flex-shrink-0 flex items-center space-x-2">
            <Button
              id="status-banner-verify-btn"
              variant={isVerified ? 'success' : isTampered ? 'danger' : 'secondary'}
              size="md"
              portalTheme="auditor"
              onClick={handleRun}
              disabled={isRunning}
              loading={isRunning}
              leftIcon={isVerified ? <RefreshCw className="w-4 h-4" /> : <Play className="w-4 h-4" />}
            >
              Run Verification
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
}
