import { Anchor, ExternalLink, Clock, GitCommit } from 'lucide-react';
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
    border: 'border-emerald-500/30',
    bg: 'bg-[#0F172A]/80',
    pillBg: 'bg-emerald-500/15 text-emerald-300 border-emerald-500/30',
    dot: 'bg-emerald-400 shadow-[0_0_8px_rgba(52,211,153,0.8)]',
    icon: 'text-emerald-400',
    glow: 'shadow-[0_0_24px_rgba(52,211,153,0.06)]',
  },
  STALE: {
    border: 'border-amber-500/30',
    bg: 'bg-[#0F172A]/80',
    pillBg: 'bg-amber-500/15 text-amber-300 border-amber-500/30',
    dot: 'bg-amber-400 shadow-[0_0_6px_rgba(245,158,11,0.6)]',
    icon: 'text-amber-400',
    glow: '',
  },
  MISSING: {
    border: 'border-rose-500/35',
    bg: 'bg-[#0F172A]/80',
    pillBg: 'bg-rose-500/15 text-rose-300 border-rose-500/35',
    dot: 'bg-rose-500 animate-pulse',
    icon: 'text-rose-400',
    glow: '',
  },
  MISMATCH: {
    border: 'border-rose-500/50',
    bg: 'bg-rose-950/20',
    pillBg: 'bg-rose-500/25 text-rose-200 border-rose-500/50',
    dot: 'bg-rose-500 shadow-[0_0_10px_rgba(244,63,94,0.9)] animate-ping',
    icon: 'text-rose-400',
    glow: 'shadow-[0_0_30px_rgba(244,63,94,0.18)]',
  },
};

export default function AnchorStatus({ data }: AnchorStatusProps) {
  const style = STATUS_STYLES[data.status] || STATUS_STYLES.MISSING;

  return (
    <div
      className={`rounded-2xl border p-5 flex flex-col space-y-4 ${style.border} ${style.bg} ${style.glow} transition-[border-color,background-color] duration-150 shadow-sm`}
    >
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center space-x-2.5">
          <div
            className={`w-9 h-9 rounded-xl flex items-center justify-center bg-slate-800 border ${style.border}`}
          >
            <Anchor className={`w-4 h-4 ${style.icon}`} />
          </div>
          <div>
            <p className="text-xs text-slate-500 uppercase tracking-wider font-semibold">Cryptographic Anchor</p>
            <h3 className="text-sm font-semibold text-slate-200">External Checkpoint</h3>
          </div>
        </div>
        <span className={`flex items-center space-x-1.5 px-2.5 py-1 rounded-full text-[11px] font-bold uppercase tracking-wider border ${style.pillBg}`}>
          <span className={`w-1.5 h-1.5 rounded-full ${style.dot}`} />
          <span>{data.status}</span>
        </span>
      </div>

      {/* Divider */}
      <div className="border-t border-slate-700/40" />

      {/* Details grid */}
      <div className="grid grid-cols-1 gap-3">
        {/* Store location */}
        <div className="flex items-start space-x-3">
          <ExternalLink className="w-3.5 h-3.5 text-slate-500 mt-0.5 flex-shrink-0" />
          <div>
            <p className="text-[10px] uppercase tracking-wider text-slate-600 font-semibold mb-0.5">
              Anchor Store
            </p>
            <p className="text-xs font-mono text-slate-300 break-all">{data.anchor_location}</p>
            <p className="text-[10px] text-slate-600 capitalize mt-0.5">
              {data.anchor_store.replace('_', ' ')}
            </p>
          </div>
        </div>

        {/* Last anchored */}
        <div className="flex items-start space-x-3">
          <Clock className="w-3.5 h-3.5 text-slate-500 mt-0.5 flex-shrink-0" />
          <div>
            <p className="text-[10px] uppercase tracking-wider text-slate-600 font-semibold mb-0.5">
              Last Anchored
            </p>
            <p className="text-xs text-slate-300">{formatTimestamp(data.last_anchored)}</p>
            <p className="text-[10px] text-slate-600 mt-0.5">
              {new Date(data.last_anchored).toLocaleString()}
            </p>
          </div>
        </div>

        {/* Anchor hash */}
        <div className="flex items-start space-x-3">
          <GitCommit className="w-3.5 h-3.5 text-slate-500 mt-0.5 flex-shrink-0" />
          <div>
            <p className="text-[10px] uppercase tracking-wider text-slate-600 font-semibold mb-0.5">
              Anchor Hash
            </p>
            <p className="text-[11px] font-mono text-violet-400/80 bg-violet-500/5 border border-violet-500/15 px-2 py-1 rounded break-all">
              {data.anchor_hash}
            </p>
          </div>
        </div>
      </div>

      {/* Footer: entries since anchor */}
      <div className="border-t border-slate-700/40 pt-3">
        <div className="flex items-center justify-between">
          <p className="text-xs text-slate-500">
            Entries since last anchor
          </p>
          <span
            className={`text-sm font-bold font-mono ${
              data.entries_since_anchor > 100 ? 'text-amber-400' : 'text-slate-300'
            }`}
          >
            {data.entries_since_anchor.toLocaleString()}
          </span>
        </div>
        {data.entries_since_anchor > 100 && (
          <p className="text-[10px] text-amber-500/70 mt-1">Consider triggering a new checkpoint soon.</p>
        )}
      </div>
    </div>
  );
}
