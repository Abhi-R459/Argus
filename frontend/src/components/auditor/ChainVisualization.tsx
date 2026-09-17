import { useState } from 'react';
import { ChevronDown, ChevronUp, Hash, ArrowRight } from 'lucide-react';
import type { ChainEntry, AuditOperation, Severity } from '../../services/auditService';

interface ChainVisualizationProps {
  entries: ChainEntry[];
  tamperedSequenceId?: number | null;
}

const OPERATION_STYLES: Record<AuditOperation, string> = {
  INSERT: 'bg-linear-success/15 text-linear-success border-linear-success/30',
  UPDATE: 'bg-linear-primary/15 text-linear-primary border-linear-primary/30',
  DELETE: 'bg-grafana-orange/15 text-grafana-orange border-grafana-orange/30',
};

const SEVERITY_DOT: Record<Severity, string> = {
  low: 'bg-linear-ink-subtle',
  medium: 'bg-linear-primary',
  high: 'bg-grafana-orange',
  critical: 'bg-grafana-orange',
};

const SEVERITY_ROW_GLOW: Record<Severity, string> = {
  low: '',
  medium: '',
  high: 'bg-grafana-orange/5',
  critical: 'bg-grafana-orange/10 border-l-2 border-grafana-orange/50',
};

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
  return date.toLocaleDateString();
}

function truncateHash(hash: string, start = 6, end = 4): string {
  if (hash.length <= start + end + 3) return hash;
  return `${hash.slice(0, start)}…${hash.slice(-end)}`;
}

interface DiffRowProps {
  label: string;
  oldVal: unknown;
  newVal: unknown;
}

function DiffRow({ label, oldVal, newVal }: DiffRowProps) {
  const hasChanged = JSON.stringify(oldVal) !== JSON.stringify(newVal);
  return (
    <tr className={hasChanged ? 'bg-linear-surface-3/50' : ''}>
      <td className="py-1.5 pr-4 text-xs text-linear-ink-subtle font-mono align-top whitespace-nowrap">{label}</td>
      <td className="py-1.5 pr-4 text-xs font-mono align-top">
        {oldVal !== undefined && oldVal !== null ? (
          <span className={hasChanged ? 'text-grafana-orange line-through opacity-80' : 'text-linear-ink-subtle'}>
            {String(oldVal)}
          </span>
        ) : (
          <span className="text-linear-ink-tertiary italic">—</span>
        )}
      </td>
      <td className="py-1.5 text-xs font-mono align-top">
        {newVal !== undefined && newVal !== null ? (
          <span className={hasChanged ? 'text-linear-success font-semibold' : 'text-linear-ink-subtle'}>
            {String(newVal)}
          </span>
        ) : (
          <span className="text-linear-ink-tertiary italic">—</span>
        )}
      </td>
    </tr>
  );
}

interface DiffDrawerProps {
  entry: ChainEntry;
}

function DiffDrawer({ entry }: DiffDrawerProps) {
  const allKeys = Array.from(
    new Set([
      ...Object.keys(entry.old_value ?? {}),
      ...Object.keys(entry.new_value ?? {}),
    ])
  );

  return (
    <div className="px-6 py-4 bg-linear-surface-2 border-t border-linear-hairline">
      <div className="flex items-center space-x-6 mb-3">
        {/* Hash chain link */}
        <div className="flex items-center space-x-2 text-xs font-mono text-linear-ink-subtle">
          <Hash className="w-3 h-3" />
          <span className="text-linear-primary">{truncateHash(entry.prev_hash ?? 'genesis', 10, 8)}</span>
          <ArrowRight className="w-3 h-3 text-linear-ink-tertiary" />
          <span className="text-linear-primary">{truncateHash(entry.hash, 10, 8)}</span>
        </div>
      </div>

      {allKeys.length === 0 ? (
        <p className="text-xs text-linear-ink-subtle italic">No field-level diff available.</p>
      ) : (
        <div className="overflow-x-auto no-scrollbar">
          <table className="min-w-full">
            <thead>
              <tr>
                <th className="pb-2 text-left text-[10px] uppercase tracking-wider text-linear-ink-subtle pr-4">Field</th>
                <th className="pb-2 text-left text-[10px] uppercase tracking-wider text-grafana-orange/80 pr-4">Before</th>
                <th className="pb-2 text-left text-[10px] uppercase tracking-wider text-linear-success/80">After</th>
              </tr>
            </thead>
            <tbody>
              {allKeys.map((key) => (
                <DiffRow
                  key={key}
                  label={key}
                  oldVal={entry.old_value?.[key]}
                  newVal={entry.new_value?.[key]}
                />
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

interface ChainRowProps {
  entry: ChainEntry;
  isFirst: boolean;
  isTampered?: boolean;
}

function ChainRow({ entry, isFirst, isTampered }: ChainRowProps) {
  const [expanded, setExpanded] = useState(false);

  return (
    <>
      <tr
        className={`group cursor-pointer transition-colors duration-150 ${
          isTampered
            ? 'bg-grafana-orange/15 border-l-4 border-grafana-orange'
            : `${SEVERITY_ROW_GLOW[entry.severity]} ${expanded ? 'bg-linear-surface-2' : 'hover:bg-linear-surface-2/60'}`
        }`}
        onClick={() => setExpanded((v) => !v)}
        title={isTampered ? 'Tampered row detected! Click to expand diff' : 'Click to expand diff'}
      >
        {/* Entry ID & hash chain connector */}
        <td className="px-2.5 sm:px-3 py-2.5 whitespace-nowrap">
          <div className="flex items-center space-x-2">
            {/* Chain connector dot */}
            <div className="flex flex-col items-center">
              <div
                className={`w-2 h-2 rounded-full flex-shrink-0 ${
                  isTampered
                    ? 'bg-grafana-orange'
                    : SEVERITY_DOT[entry.severity]
                }`}
              />
              {!isFirst && <div className="w-0.5 h-3.5 bg-linear-hairline mt-0.5" />}
            </div>
            <span className={`text-xs font-mono font-semibold ${isTampered ? 'text-grafana-orange font-bold' : 'text-linear-ink'}`}>
              #{entry.entry_id}
            </span>
            {isTampered && (
              <span className="ml-1 px-1 py-0.5 rounded text-[9px] font-bold bg-grafana-orange/30 text-white border border-grafana-orange/60 animate-pulse">
                ALERT
              </span>
            )}
          </div>
        </td>

        {/* Hash */}
        <td className="px-2 sm:px-2.5 py-2.5 whitespace-nowrap">
          <span className={`text-[11px] font-mono px-1.5 py-0.5 rounded border ${
            isTampered
              ? 'text-white bg-grafana-orange/30 border-grafana-orange/50 font-semibold'
              : 'text-linear-primary bg-linear-primary/5 border-linear-primary/20'
          }`}>
            {truncateHash(entry.hash)}
          </span>
        </td>

        {/* Operation */}
        <td className="px-2 sm:px-2.5 py-2.5 whitespace-nowrap">
          <span
            className={`inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-bold uppercase tracking-wider border ${
              OPERATION_STYLES[entry.operation]
            }`}
          >
            {entry.operation}
          </span>
        </td>

        {/* Table */}
        <td className="px-2 sm:px-2.5 py-2.5 whitespace-nowrap">
          <span className="text-xs font-mono text-linear-ink-muted">{entry.table_name}</span>
        </td>

        {/* Actor */}
        <td className="px-2 sm:px-2.5 py-2.5 whitespace-nowrap">
          <div className="flex items-center space-x-1.5">
            <div className="w-4.5 h-4.5 rounded-full bg-linear-surface-3 border border-linear-hairline-strong flex items-center justify-center text-[9px] font-bold text-linear-primary uppercase shrink-0">
              {entry.actor_email.charAt(0)}
            </div>
            <span className="text-xs text-linear-ink-muted max-w-[100px] sm:max-w-[125px] truncate" title={entry.actor_email}>
              {entry.actor_email}
            </span>
          </div>
        </td>

        {/* Timestamp */}
        <td className="px-2 sm:px-2.5 py-2.5 whitespace-nowrap">
          <span className="text-[11px] text-linear-ink-subtle">{formatTimestamp(entry.timestamp)}</span>
        </td>

        {/* Severity */}
        <td className="px-2 sm:px-2.5 py-2.5 whitespace-nowrap">
          <div className="flex items-center space-x-1.5">
            <span className={`w-1.5 h-1.5 rounded-full ${SEVERITY_DOT[entry.severity]}`} />
            <span
              className={`text-xs capitalize ${
                entry.severity === 'critical'
                  ? 'text-grafana-orange font-semibold'
                  : entry.severity === 'high'
                  ? 'text-grafana-orange'
                  : entry.severity === 'medium'
                  ? 'text-linear-primary'
                  : 'text-linear-ink-subtle'
              }`}
            >
              {entry.severity}
            </span>
          </div>
        </td>

        {/* Expand toggle */}
        <td className="px-2 sm:px-3 py-2.5 text-right w-8">
          <div className="text-linear-ink-tertiary group-hover:text-linear-ink-subtle transition-colors">
            {expanded ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
          </div>
        </td>
      </tr>

      {/* Expandable diff drawer */}
      {expanded && (
        <tr>
          <td colSpan={8} className="p-0">
            <DiffDrawer entry={entry} />
          </td>
        </tr>
      )}
    </>
  );
}

export default function ChainVisualization({ entries, tamperedSequenceId }: ChainVisualizationProps) {
  return (
    <div className="bg-linear-surface-1 border border-linear-hairline rounded-2xl overflow-hidden shadow-sm">
      {/* Header */}
      <div className="flex items-center justify-between px-6 py-4 border-b border-linear-hairline bg-linear-surface-2/40">
        <div className="flex items-center space-x-3">
          <Hash className="w-5 h-5 text-linear-primary" />
          <h3 className="text-sm font-semibold text-linear-ink">Audit Hash Chain</h3>
          <span className="text-xs text-linear-ink-muted bg-linear-surface-2 px-2 py-0.5 rounded border border-linear-hairline">
            {entries.length} entries
          </span>
          {tamperedSequenceId && (
            <span className="text-xs text-white bg-grafana-orange/30 border border-grafana-orange/50 px-2.5 py-0.5 rounded-full font-mono animate-pulse flex items-center space-x-1.5">
              <span className="w-1.5 h-1.5 rounded-full bg-grafana-orange" />
              <span>Violation at #{tamperedSequenceId}</span>
            </span>
          )}
        </div>
        <span className="text-xs text-linear-ink-subtle italic">Click any row to expand diff</span>
      </div>

      {/* Table - styled with no-scrollbar to eliminate bottom scrollbar */}
      <div className="overflow-x-auto no-scrollbar">
        <table className="w-full text-left border-collapse">
          <thead className="bg-linear-surface-2/60">
            <tr>
              {[
                { label: 'Entry', className: 'text-left px-2.5 sm:px-3' },
                { label: 'Hash', className: 'text-left px-2 sm:px-2.5' },
                { label: 'Op', className: 'text-left px-2 sm:px-2.5' },
                { label: 'Table', className: 'text-left px-2 sm:px-2.5' },
                { label: 'Actor', className: 'text-left px-2 sm:px-2.5' },
                { label: 'When', className: 'text-left px-2 sm:px-2.5' },
                { label: 'Severity', className: 'text-left px-2 sm:px-2.5' },
                { label: '', className: 'text-right px-2 sm:px-3 w-8' },
              ].map((h, idx) => (
                <th
                  key={idx}
                  className={`py-2 text-[10px] font-semibold uppercase tracking-wider text-linear-ink-subtle ${h.className}`}
                >
                  {h.label}
                </th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-linear-hairline">
            {entries.map((entry, i) => (
              <ChainRow
                key={entry.entry_id}
                entry={entry}
                isFirst={i === entries.length - 1}
                isTampered={entry.entry_id === tamperedSequenceId}
              />
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
