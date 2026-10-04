import { Anchor, ExternalLink, Clock, GitCommit, ShieldCheck, CheckCircle2, XCircle } from 'lucide-react';
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
    border: 'border-grafana-orange/30',
    bg: 'bg-linear-surface-1',
    pillBg: 'bg-grafana-orange/15 text-grafana-orange border-grafana-orange/30',
    dot: 'bg-grafana-orange',
    icon: 'text-grafana-orange',
    glow: 'shadow-xs',
  },
  MISSING: {
    border: 'border-grafana-orange/40',
    bg: 'bg-linear-surface-1',
    pillBg: 'bg-grafana-orange/15 text-grafana-orange border-grafana-orange/35',
    dot: 'bg-grafana-orange',
    icon: 'text-grafana-orange',
    glow: 'shadow-xs',
  },
  MISMATCH: {
    border: 'border-grafana-orange/60',
    bg: 'bg-grafana-orange/15',
    pillBg: 'bg-grafana-orange/25 text-white border-grafana-orange/50',
    dot: 'bg-grafana-orange',
    icon: 'text-grafana-orange',
    glow: 'shadow-xs',
  },
};

export default function AnchorStatus({ data }: AnchorStatusProps) {
  const style = STATUS_STYLES[data.status] || STATUS_STYLES.MISSING;

  return (
    <div
      className={`rounded-2xl border flex flex-col justify-between overflow-hidden shadow-sm h-full ${style.border} ${style.bg} ${style.glow} transition-[border-color,background-color] duration-150`}
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
            <p className="text-[10px] text-linear-ink-subtle uppercase tracking-wider font-semibold">Cryptographic Anchor</p>
            <h3 className="text-sm font-semibold text-linear-ink">External Checkpoint</h3>
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
            <p className="text-[10px] uppercase tracking-wider text-linear-ink-subtle font-semibold mb-0.5">
              Anchor Store
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
            <p className="text-[10px] uppercase tracking-wider text-linear-ink-subtle font-semibold mb-0.5">
              Last Anchored
            </p>
            <p className="text-xs text-linear-ink-muted">{formatTimestamp(data.last_anchored)}</p>
            <p className="text-[10px] text-linear-ink-subtle mt-0.5">
              {new Date(data.last_anchored).toLocaleString()}
            </p>
          </div>
        </div>

        {/* Anchor hash */}
        <div className="flex items-start space-x-3">
          <GitCommit className="w-3.5 h-3.5 text-linear-ink-subtle mt-0.5 flex-shrink-0" />
          <div>
            <p className="text-[10px] uppercase tracking-wider text-linear-ink-subtle font-semibold mb-0.5">
              Anchor Hash
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
              <p className="text-[11px] uppercase tracking-wider text-linear-ink font-semibold">
                Witness Quorum (RFC 9162)
              </p>
            </div>
            <span
              className={`flex items-center space-x-1 px-2 py-0.5 rounded-full text-[10px] font-bold uppercase tracking-wider border ${
                data.witness_report.quorum_satisfied
                  ? 'bg-linear-success/15 text-linear-success border-linear-success/30'
                  : 'bg-grafana-orange/15 text-grafana-orange border-grafana-orange/30'
              }`}
            >
              {data.witness_report.quorum_satisfied ? (
                <CheckCircle2 className="w-2.5 h-2.5" />
              ) : (
                <XCircle className="w-2.5 h-2.5" />
              )}
              <span>
                {data.witness_report.cosigned_witnesses}/{data.witness_report.total_witnesses} Cosigned
              </span>
            </span>
          </div>

          <p className="text-[11px] text-linear-ink-subtle leading-relaxed">
            Threshold: <strong className="text-linear-ink font-semibold">{data.witness_report.required_threshold}-of-{data.witness_report.total_witnesses}</strong> quorum verified. Mitigates split-view & equivocation attacks.
          </p>

          <div className="space-y-1.5 bg-linear-surface-2 p-2.5 rounded-xl border border-linear-hairline">
            {data.witness_report.per_witness.map((w, idx) => {
              const isValid = w.status === 'VALID';
              return (
                <div
                  key={idx}
                  className="flex items-center justify-between text-[11px] py-1 px-1.5 rounded hover:bg-linear-surface-1 transition-colors"
                >
                  <div className="flex items-center space-x-2 truncate pr-2">
                    <span
                      className={`w-1.5 h-1.5 rounded-full flex-shrink-0 ${
                        isValid ? 'bg-linear-success' : 'bg-grafana-orange'
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
                          : 'bg-grafana-orange/10 text-grafana-orange border-grafana-orange/30'
                      }`}
                    >
                      {w.status}
                    </span>
                  </div>
                </div>
              );
            })}
          </div>
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
              data.entries_since_anchor > 100 ? 'text-grafana-orange' : 'text-linear-ink'
            }`}
          >
            {data.entries_since_anchor.toLocaleString()}
          </span>
        </div>
        {data.entries_since_anchor > 100 && (
          <p className="text-[10px] text-grafana-orange/80 mt-1">Consider triggering a new checkpoint soon.</p>
        )}
      </div>
    </div>
  );
}
