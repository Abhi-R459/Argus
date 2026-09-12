import { useState } from 'react';
import { ChevronDown, ChevronUp, Hash, ArrowRight } from 'lucide-react';
import type { ChainEntry, AuditOperation, Severity } from '../../services/auditService';

interface ChainVisualizationProps {
  entries: ChainEntry[];
}

const OPERATION_STYLES: Record<AuditOperation, string> = {
  INSERT: 'bg-emerald-500/15 text-emerald-300 border-emerald-500/25',
  UPDATE: 'bg-amber-500/15 text-amber-300 border-amber-500/25',
  DELETE: 'bg-red-500/15 text-red-300 border-red-500/25',
};

const SEVERITY_DOT: Record<Severity, string> = {
  low: 'bg-slate-400',
  medium: 'bg-amber-400',
  high: 'bg-orange-400',
  critical: 'bg-red-500 shadow-[0_0_6px_rgba(239,68,68,0.7)]',
};

const SEVERITY_ROW_GLOW: Record<Severity, string> = {
  low: '',
  medium: '',
  high: 'bg-orange-500/3',
  critical: 'bg-red-500/5 border-l-2 border-red-500/30',
};

function formatTimestamp(isoString: string): string {
  const date = new Date(isoString);
  const diff = Date.now() - date.getTime();
  const minutes = Math.floor(diff / 60000);
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  return date.toLocaleDateString();
}

function truncateHash(hash: string, start = 8, end = 6): string {
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
    <tr className={hasChanged ? 'bg-amber-500/5' : ''}>
      <td className="py-1.5 pr-4 text-xs text-slate-500 font-mono align-top whitespace-nowrap">{label}</td>
      <td className="py-1.5 pr-4 text-xs font-mono align-top">
        {oldVal !== undefined && oldVal !== null ? (
          <span className={hasChanged ? 'text-red-400 line-through opacity-70' : 'text-slate-400'}>
            {String(oldVal)}
          </span>
        ) : (
          <span className="text-slate-600 italic">—</span>
        )}
      </td>
      <td className="py-1.5 text-xs font-mono align-top">
        {newVal !== undefined && newVal !== null ? (
          <span className={hasChanged ? 'text-emerald-400 font-semibold' : 'text-slate-400'}>
            {String(newVal)}
          </span>
        ) : (
          <span className="text-slate-600 italic">—</span>
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
    <div className="px-6 py-4 bg-slate-900/70 border-t border-slate-700/50">
      <div className="flex items-center space-x-6 mb-3">
        {/* Hash chain link */}
        <div className="flex items-center space-x-2 text-xs font-mono text-slate-500">
          <Hash className="w-3 h-3" />
          <span className="text-violet-400">{truncateHash(entry.prev_hash ?? 'genesis', 10, 8)}</span>
          <ArrowRight className="w-3 h-3 text-slate-600" />
          <span className="text-violet-300">{truncateHash(entry.hash, 10, 8)}</span>
        </div>
      </div>

      {allKeys.length === 0 ? (
        <p className="text-xs text-slate-600 italic">No field-level diff available.</p>
      ) : (
        <div className="overflow-x-auto">
          <table className="min-w-full">
            <thead>
              <tr>
                <th className="pb-2 text-left text-[10px] uppercase tracking-wider text-slate-600 pr-4">Field</th>
                <th className="pb-2 text-left text-[10px] uppercase tracking-wider text-red-500/70 pr-4">Before</th>
                <th className="pb-2 text-left text-[10px] uppercase tracking-wider text-emerald-500/70">After</th>
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
}

function ChainRow({ entry, isFirst }: ChainRowProps) {
  const [expanded, setExpanded] = useState(false);

  return (
    <>
      <tr
        className={`group cursor-pointer transition-colors duration-150 ${
          SEVERITY_ROW_GLOW[entry.severity]
        } ${expanded ? 'bg-slate-800/60' : 'hover:bg-slate-800/40'}`}
        onClick={() => setExpanded((v) => !v)}
        title="Click to expand diff"
      >
        {/* Entry ID & hash chain connector */}
        <td className="px-4 py-3 whitespace-nowrap">
          <div className="flex items-center space-x-2">
            {/* Chain connector dot */}
            <div className="flex flex-col items-center">
              <div
                className={`w-2 h-2 rounded-full flex-shrink-0 ${SEVERITY_DOT[entry.severity]}`}
              />
              {!isFirst && <div className="w-0.5 h-4 bg-slate-700 mt-0.5" />}
            </div>
            <span className="text-sm font-mono text-slate-300">#{entry.entry_id}</span>
          </div>
        </td>

        {/* Hash */}
        <td className="px-4 py-3 whitespace-nowrap">
          <span className="text-xs font-mono text-violet-400/80 bg-violet-500/5 border border-violet-500/15 px-2 py-0.5 rounded">
            {truncateHash(entry.hash)}
          </span>
        </td>

        {/* Operation */}
        <td className="px-4 py-3 whitespace-nowrap">
          <span
            className={`inline-flex items-center px-2 py-0.5 rounded-md text-[11px] font-bold uppercase tracking-wider border ${
              OPERATION_STYLES[entry.operation]
            }`}
          >
            {entry.operation}
          </span>
        </td>

        {/* Table */}
        <td className="px-4 py-3 whitespace-nowrap">
          <span className="text-xs font-mono text-slate-400">{entry.table_name}</span>
        </td>

        {/* Actor */}
        <td className="px-4 py-3 whitespace-nowrap">
          <div className="flex items-center space-x-2">
            <div className="w-5 h-5 rounded-full bg-indigo-500/20 border border-indigo-500/30 flex items-center justify-center text-[9px] font-bold text-indigo-300 uppercase">
              {entry.actor_email.charAt(0)}
            </div>
            <span className="text-xs text-slate-400 max-w-[140px] truncate">{entry.actor_email}</span>
          </div>
        </td>

        {/* Timestamp */}
        <td className="px-4 py-3 whitespace-nowrap">
          <span className="text-xs text-slate-500">{formatTimestamp(entry.timestamp)}</span>
        </td>

        {/* Severity */}
        <td className="px-4 py-3 whitespace-nowrap">
          <div className="flex items-center space-x-1.5">
            <span className={`w-1.5 h-1.5 rounded-full ${SEVERITY_DOT[entry.severity]}`} />
            <span
              className={`text-xs capitalize ${
                entry.severity === 'critical'
                  ? 'text-red-400 font-semibold'
                  : entry.severity === 'high'
                  ? 'text-orange-400'
                  : entry.severity === 'medium'
                  ? 'text-amber-400'
                  : 'text-slate-500'
              }`}
            >
              {entry.severity}
            </span>
          </div>
        </td>

        {/* Expand toggle */}
        <td className="px-4 py-3 text-right">
          <div className="text-slate-600 group-hover:text-slate-400 transition-colors">
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

export default function ChainVisualization({ entries }: ChainVisualizationProps) {
  return (
    <div className="bg-slate-900/50 border border-slate-700/50 rounded-2xl overflow-hidden">
      {/* Header */}
      <div className="flex items-center justify-between px-6 py-4 border-b border-slate-700/50 bg-slate-900/30">
        <div className="flex items-center space-x-3">
          <Hash className="w-5 h-5 text-violet-400" />
          <h3 className="text-sm font-semibold text-slate-200">Audit Hash Chain</h3>
          <span className="text-xs text-slate-500 bg-slate-800 px-2 py-0.5 rounded border border-slate-700">
            {entries.length} entries
          </span>
        </div>
        <span className="text-xs text-slate-600 italic">Click any row to expand diff</span>
      </div>

      {/* Table */}
      <div className="overflow-x-auto">
        <table className="min-w-full">
          <thead className="bg-slate-900/60">
            <tr>
              {['Entry', 'Hash', 'Op', 'Table', 'Actor', 'When', 'Severity', ''].map((h) => (
                <th
                  key={h}
                  className="px-4 py-2.5 text-left text-[10px] font-semibold uppercase tracking-wider text-slate-500"
                >
                  {h}
                </th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-800/60">
            {entries.map((entry, i) => (
              <ChainRow key={entry.entry_id} entry={entry} isFirst={i === entries.length - 1} />
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
