import { useState } from 'react';
import { ChevronDown, Hash, ArrowRight } from 'lucide-react';
import type { ChainEntry, Severity } from '../../services/auditService';
import DiffViewer from './DiffViewer';
import { useAccordionTransition } from '../../hooks/useAccordionTransition';
import { formatRelativeTime, truncateHash } from '../../lib/format';
import { getActionSemantic, getSeverityDotClass } from '../../lib/semantics';

interface ChainVisualizationProps {
  entries: ChainEntry[];
  tamperedSequenceId?: number | null;
}

const SEVERITY_ROW_GLOW: Record<Severity, string> = {
  low: '',
  medium: '',
  high: 'bg-grafana-orange/5',
  critical: 'bg-grafana-orange/10 border-l-2 border-grafana-orange/50',
};

interface DiffDrawerProps {
  entry: ChainEntry;
  isTampered?: boolean;
}

function DiffDrawer({ entry, isTampered }: DiffDrawerProps) {
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

      <DiffViewer
        oldValue={entry.old_value}
        newValue={entry.new_value}
        operation={entry.operation as any}
        isTampered={isTampered}
        sequenceId={entry.entry_id}
      />
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
  const { isRendered, isExpanded } = useAccordionTransition(expanded);

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
        <td className="px-2 py-2.5 whitespace-nowrap">
          <div className="flex items-center space-x-1.5">
            {/* Chain connector dot */}
            <div className="flex flex-col items-center">
              <div
                className={`w-2 h-2 rounded-full flex-shrink-0 ${
                  isTampered
                    ? 'bg-grafana-orange'
                    : getSeverityDotClass(entry.severity)
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

        {/* Hash Linkage (prev -> hash) */}
        <td className="px-2 py-2.5 whitespace-nowrap font-mono text-xs">
          <div className="flex items-center space-x-1">
            <span className="text-linear-ink-subtle text-[11px]">{truncateHash(entry.prev_hash || '0'.repeat(64), 4, 4)}</span>
            <ArrowRight className="w-2.5 h-2.5 text-linear-ink-tertiary shrink-0" />
            <span className={`text-[11px] px-1 py-0.5 rounded border ${
              isTampered
                ? 'text-white bg-grafana-orange/30 border-grafana-orange/50 font-semibold'
                : 'text-linear-primary bg-linear-primary/5 border-linear-primary/20'
            }`}>
              {truncateHash(entry.hash, 4, 4)}
            </span>
          </div>
        </td>

        {/* Operation */}
        <td className="px-2 py-2.5 whitespace-nowrap">
          <span
            className={`inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-bold uppercase tracking-wider border ${
              getActionSemantic(entry.operation, entry.table_name, 'auditor').className
            }`}
          >
            {entry.operation}
          </span>
        </td>

        {/* Table */}
        <td className="px-2 py-2.5 whitespace-nowrap">
          <span className="text-xs font-mono text-linear-ink-muted">{entry.table_name}</span>
        </td>

        {/* Actor */}
        <td className="px-2 py-2.5 whitespace-nowrap">
          <div className="flex items-center space-x-1.5">
            <div className="w-5 h-5 rounded-full bg-linear-surface-3 border border-linear-hairline-strong flex items-center justify-center text-[9px] font-bold text-linear-primary uppercase shrink-0">
              {entry.actor_email.charAt(0)}
            </div>
            <span className="text-xs text-linear-ink-muted max-w-[95px] sm:max-w-[110px] truncate" title={entry.actor_email}>
              {entry.actor_email}
            </span>
          </div>
        </td>

        {/* Timestamp */}
        <td className="px-2 py-2.5 whitespace-nowrap">
          <span className="text-[11px] text-linear-ink-subtle" title={new Date(entry.timestamp).toLocaleString()}>
            {formatRelativeTime(entry.timestamp)}
          </span>
        </td>

        {/* Severity */}
        <td className="px-2 py-2.5 whitespace-nowrap">
          <div className="flex items-center space-x-1.5">
            <span className={`w-1.5 h-1.5 rounded-full ${getSeverityDotClass(entry.severity)}`} />
            <span
              className={`text-xs capitalize ${
                entry.severity === 'critical'
                  ? 'text-grafana-orange font-semibold'
                  : entry.severity === 'high'
                  ? 'text-grafana-orange'
                  : entry.severity === 'medium'
                  ? 'text-amber-400'
                  : 'text-linear-ink-subtle'
              }`}
            >
              {entry.severity}
            </span>
          </div>
        </td>

        {/* Expand toggle with smooth 180-deg chevron rotation */}
        <td className="px-2 py-2.5 text-right w-7">
          <div className="text-linear-ink-tertiary group-hover:text-linear-ink-subtle transition-colors">
            <span
              className={`inline-flex items-center justify-center transition-transform duration-160 ease-out ${
                expanded ? 'rotate-180 text-linear-ink' : 'rotate-0'
              }`}
            >
              <ChevronDown className="w-4 h-4" />
            </span>
          </div>
        </td>
      </tr>

      {/* Expandable diff drawer with smooth slide down / slide up */}
      {isRendered && (
        <tr>
          <td colSpan={8} className="p-0 border-b border-linear-hairline">
            <div className={`accordion-collapse ${isExpanded ? 'accordion-open' : ''}`}>
              <div className="accordion-collapse-inner">
                <DiffDrawer entry={entry} isTampered={isTampered} />
              </div>
            </div>
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

      {/* Table */}
      <div className="overflow-x-auto">
        <table className="w-full text-left border-collapse">
          <thead className="bg-linear-surface-2/60">
            <tr>
              {[
                { label: 'Entry', className: 'text-left px-2' },
                { label: 'Hash Linkage', className: 'text-left px-2' },
                { label: 'Op', className: 'text-left px-2' },
                { label: 'Table', className: 'text-left px-2' },
                { label: 'Actor', className: 'text-left px-2' },
                { label: 'When', className: 'text-left px-2' },
                { label: 'Severity', className: 'text-left px-2' },
                { label: '', className: 'text-right px-2 w-7' },
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
