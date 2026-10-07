import { Anchor, ExternalLink, Clock, GitCommit, ShieldCheck, CheckCircle2, HelpCircle, XCircle } from 'lucide-react';
import type { AnchorInfo } from '../../services/auditService';

interface AnchorStatusProps {
  data: AnchorInfo;
}

function formatTimestamp(isoString: string): string {
  const date = new Date(isoString);
  const diff = Math.max(0, Date.now() - date.getTime());
  const seconds = Math.floor(diff / 1000);
  if (seconds < 5) return 'just now';
  if (seconds < 60) return `${seconds}s ago`;
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  return `${days}d ago`;
}

const STATUS_STYLES = {
  ANCHORED: {
    border: 'border-linear-success/30',
    bg: 'bg-linear-surface-1',
    pillBg: 'bg-linear-success/15 text-linear-success border-linear-success/30',
    dot: 'bg-linear-success',
    icon: 'text-linear-success',
    glow: 'shadow-xs',
  },
  STALE: {
    border: 'border-status-warning/30',
    bg: 'bg-linear-surface-1',
    pillBg: 'bg-status-warning/15 text-status-warning border-status-warning/30',
    dot: 'bg-status-warning',
    icon: 'text-status-warning',
    glow: 'shadow-xs',
  },
  MISSING: {
    border: 'border-status-warning/40',
    bg: 'bg-linear-surface-1',
    pillBg: 'bg-status-warning/15 text-status-warning border-status-warning/35',
    dot: 'bg-status-warning',
    icon: 'text-status-warning',
    glow: 'shadow-xs',
  },
  MISMATCH: {
    border: 'border-status-warning/60',
    bg: 'bg-status-warning/15',
    pillBg: 'bg-status-warning/25 text-white border-status-warning/50',
    dot: 'bg-status-warning',
    icon: 'text-status-warning',
    glow: 'shadow-xs',
  },
  UNVERIFIED: {
    border: 'border-linear-hairline',
    bg: 'bg-linear-surface-1',
    pillBg: 'bg-linear-surface-2 text-linear-ink-muted border-linear-hairline',
    dot: 'bg-linear-ink-muted',
    icon: 'text-linear-ink-muted',
    glow: 'shadow-xs',
  },
};

export default function AnchorStatus({ data }: AnchorStatusProps) {
  const style = STATUS_STYLES[data.status] || STATUS_STYLES.MISSING;
  const witnessStatus = data.witness_report?.verification_status ??
    (data.witness_report?.quorum_satisfied ? 'pass' : 'fail');

  return (
    <div
      className={`rounded-2xl border flex flex-col justify-between overflow-hidden shadow-sm ${style.border} ${style.bg} ${style.glow} transition-[border-color,background-color] duration-150`}
    >
      {/* Header */}
      <div className="flex items-center justify-between px-5 py-4 border-b border-linear-hairline shrink-0">
        <div className="flex items-center space-x-2.5">
          <div
            className={`w-9 h-9 rounded-xl flex items-center justify-center bg-linear-surface-2 border ${style.border}`}
          >
            <Anchor className={`w-4 h-4 ${style.icon}`} />
          </div>
          <div>
            <p className="text-xs text-linear-ink-subtle font-medium">Cryptographic anchor</p>
            <h3 className="text-base font-semibold text-linear-ink">Checkpoint anchor</h3>
          </div>
        </div>
        <span className={`flex items-center space-x-1.5 px-2.5 py-1 rounded-full text-[11px] font-bold uppercase tracking-wider border ${style.pillBg}`}>
          <span className={`w-1.5 h-1.5 rounded-full ${style.dot}`} />
          <span>{data.status}</span>
        </span>
      </div>

      {/* Details body */}
      <div className="p-5 flex-1 flex flex-col justify-between space-y-3.5">
        <div className="grid grid-cols-1 gap-3">
        {/* Store location */}
        <div className="flex items-start space-x-3">
          <ExternalLink className="w-3.5 h-3.5 text-linear-ink-subtle mt-0.5 flex-shrink-0" />
          <div>
            <p className="text-xs text-linear-ink-subtle font-medium mb-0.5">
              Anchor store
            </p>
            <p className="text-xs font-mono text-linear-ink-muted break-all">{data.anchor_location}</p>
            <p className="text-[10px] text-linear-ink-subtle capitalize mt-0.5">
              {data.anchor_store.replace('_', ' ')}
            </p>
          </div>
        </div>

        {/* Last anchored */}
        <div className="flex items-start space-x-3">
          <Clock className="w-3.5 h-3.5 text-linear-ink-subtle mt-0.5 flex-shrink-0" />
          <div>
            <p className="text-xs text-linear-ink-subtle font-medium mb-0.5">
              {data.status === 'ANCHORED' || data.status === 'STALE'
                ? (data.last_anchored ? 'Anchor record time' : 'Anchor timestamp unavailable')
                : 'Latest checkpoint time'}
            </p>
            {data.last_anchored ? (
              <>
                <p className="text-xs text-linear-ink-muted">{formatTimestamp(data.last_anchored)}</p>
                <p className="text-[10px] text-linear-ink-subtle mt-0.5">
                  {new Date(data.last_anchored).toLocaleString()}
                </p>
              </>
            ) : (
              <p className="text-xs text-linear-ink-muted">
                {data.status === 'ANCHORED' || data.status === 'STALE'
                  ? 'This anchor record does not contain a write timestamp.'
                  : 'No anchor write timestamp is available.'}
              </p>
            )}
          </div>
        </div>

        {/* Anchor hash */}
        <div className="flex items-start space-x-3">
          <GitCommit className="w-3.5 h-3.5 text-linear-ink-subtle mt-0.5 flex-shrink-0" />
          <div>
            <p className="text-xs text-linear-ink-subtle font-medium mb-0.5">
              Anchor hash
            </p>
            <p className="text-[11px] font-mono text-linear-primary bg-linear-primary/5 border border-linear-primary/15 px-2 py-1 rounded break-all">
              {data.anchor_hash}
            </p>
          </div>
        </div>
      </div>

      {/* Multi-Witness Quorum Telemetry (RFC 9162 / NOVEL-010) */}
      {data.witness_report && (
        <div className="border-t border-linear-hairline pt-3.5 space-y-3">
          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-2">
              <ShieldCheck className="w-3.5 h-3.5 text-linear-primary" />
              <p className="text-xs text-linear-ink font-semibold">
                Witness quorum <span className="font-mono text-linear-ink-subtle">· RFC 9162</span>
              </p>
            </div>
            <span
              className={`flex items-center space-x-1 px-2 py-0.5 rounded-full text-[10px] font-bold uppercase tracking-wider border ${
                witnessStatus === 'pass'
                  ? 'bg-linear-success/15 text-linear-success border-linear-success/30'
                  : witnessStatus === 'unknown'
                    ? 'bg-linear-surface-2 text-linear-ink-muted border-linear-hairline'
                    : 'bg-status-warning/15 text-status-warning border-status-warning/30'
              }`}
            >
              {witnessStatus === 'pass' ? (
                <CheckCircle2 className="w-2.5 h-2.5" />
              ) : witnessStatus === 'unknown' ? (
                <HelpCircle className="w-2.5 h-2.5" />
              ) : (
                <XCircle className="w-2.5 h-2.5" />
              )}
              <span>
                {witnessStatus === 'pass'
                  ? `${data.witness_report.cosigned_witnesses} of ${data.witness_report.total_witnesses} verified`
                  : witnessStatus === 'unknown' ? 'Unverified' : 'Quorum failed'}
              </span>
            </span>
          </div>

          <p className="text-[11px] text-linear-ink-subtle leading-relaxed">
            {witnessStatus === 'pass'
              ? <>Threshold: <strong className="text-linear-ink font-semibold">{data.witness_report.required_threshold}-of-{data.witness_report.total_witnesses}</strong> quorum verified.</>
              : data.witness_report.message ?? 'Witness quorum is not verified.'}
          </p>

          {data.witness_report.independent_trust_domains === false && (
            <p className="rounded-md border border-linear-hairline bg-linear-surface-2 px-2.5 py-2 text-[10px] text-linear-ink-muted">
              Reference implementation: witnesses run in-process and do not represent independent trust domains.
            </p>
          )}

          {data.witness_report.per_witness.length > 0 && (
            <div className="space-y-1.5 bg-linear-surface-2 p-2.5 rounded-xl border border-linear-hairline">
              {data.witness_report.per_witness.map((w, idx) => {
                const isValid = w.status === 'VALID';
                const isUnknown = w.status === 'UNKNOWN';
                return (
                  <div
                    key={idx}
                    className="flex items-center justify-between text-[11px] py-1 px-1.5 rounded hover:bg-linear-surface-1 transition-colors"
                  >
                    <div className="flex items-center space-x-2 truncate pr-2">
                      <span
                        className={`w-1.5 h-1.5 rounded-full flex-shrink-0 ${
                          isValid ? 'bg-linear-success' : isUnknown ? 'bg-linear-ink-muted' : 'bg-status-warning'
                        }`}
                      />
                      <span className="font-mono text-linear-ink truncate">{w.witness_name}</span>
                    </div>
                    <div className="flex items-center space-x-2 flex-shrink-0">
                      {w.signature_hex && (
                        <span className="font-mono text-[10px] text-linear-ink-subtle">
                          {w.signature_hex.slice(0, 8)}...
                        </span>
                      )}
                      <span
                        className={`text-[9px] font-bold px-1.5 py-0.5 rounded border uppercase ${
                          isValid
                            ? 'bg-linear-success/10 text-linear-success border-linear-success/30'
                            : isUnknown
                              ? 'bg-linear-surface-1 text-linear-ink-muted border-linear-hairline'
                              : 'bg-status-warning/10 text-status-warning border-status-warning/30'
                        }`}
                      >
                        {w.status}
                      </span>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      )}
      </div>

      {/* Footer: entries since anchor */}
      <div className="border-t border-linear-hairline px-5 py-3 shrink-0">
        <div className="flex items-center justify-between">
          <p className="text-xs text-linear-ink-subtle">
            Entries since last anchor
          </p>
          <span
            className={`text-xs font-bold font-mono ${
              data.entries_since_anchor > 100 ? 'text-status-warning' : 'text-linear-ink'
            }`}
          >
            {data.entries_since_anchor.toLocaleString()}
          </span>
        </div>
        {data.entries_since_anchor > 100 && (
          <p className="text-[10px] text-status-warning/80 mt-1">Consider triggering a new checkpoint soon.</p>
        )}
      </div>
    </div>
  );
}
