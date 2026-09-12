import { useState, useEffect } from 'react';
import { useSearchParams, useNavigate } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { useAuth } from '@clerk/clerk-react';
import {
  ChevronLeft, ChevronRight, Search, SlidersHorizontal,
  Hash, ChevronDown, ChevronUp, ArrowRight, GitBranch, Clock,
} from 'lucide-react';
import {
  fetchAuditLogs,
  useIncidentStatus,
  type AuditLogFilters,
  type AuditLogItem,
} from '../../services/auditService';
import DiffViewer from './DiffViewer';

// ─── Badges & colours ─────────────────────────────────────────────────────────

const ACTION_STYLE: Record<string, string> = {
  INSERT: 'bg-emerald-500/15 text-emerald-300 border-emerald-500/25',
  UPDATE: 'bg-amber-500/15  text-amber-300  border-amber-500/25',
  DELETE: 'bg-red-500/15    text-red-300    border-red-500/30',
};

const SEVERITY_STYLE: Record<string, string> = {
  INFO:     'bg-slate-700/60  text-slate-300  border-slate-600/40',
  WARNING:  'bg-amber-500/15  text-amber-300  border-amber-500/25',
  CRITICAL: 'bg-red-500/15    text-red-300    border-red-500/30',
};

const SEVERITY_DOT: Record<string, string> = {
  INFO:     'bg-slate-400',
  WARNING:  'bg-amber-400',
  CRITICAL: 'bg-red-500 shadow-[0_0_5px_rgba(239,68,68,0.7)]',
};

function truncateHash(h: string, n = 10) {
  return h.length <= n + 3 ? h : `${h.slice(0, n)}…`;
}

function relativeTime(iso: string) {
  const diff = Date.now() - new Date(iso).getTime();
  const m = Math.floor(diff / 60000);
  if (m < 1) return 'just now';
  if (m < 60) return `${m}m ago`;
  const hr = Math.floor(m / 60);
  if (hr < 24) return `${hr}h ago`;
  return `${Math.floor(hr / 24)}d ago`;
}

// ─── Expandable row ───────────────────────────────────────────────────────────

function AuditRow({
  entry,
  isTampered,
  isTargetSeq,
}: {
  entry: AuditLogItem;
  isTampered?: boolean;
  isTargetSeq?: boolean;
}) {
  const [open, setOpen] = useState(Boolean(isTargetSeq || isTampered));
  const navigate = useNavigate();

  return (
    <>
      <tr
        className={`group cursor-pointer transition-colors duration-150 ${
          isTampered
            ? 'bg-red-500/15 border-l-4 border-red-500 hover:bg-red-500/20 shadow-sm shadow-red-950/40'
            : isTargetSeq
            ? 'bg-violet-500/15 border-l-4 border-violet-500 hover:bg-violet-500/20'
            : open
            ? 'bg-slate-800/60'
            : 'hover:bg-slate-800/40'
        } ${entry.severity === 'CRITICAL' && !isTampered && !isTargetSeq ? 'border-l-2 border-red-500/40' : ''}`}
        onClick={() => setOpen((v) => !v)}
      >
        {/* Seq ID */}
        <td className="px-4 py-3 whitespace-nowrap">
          <div className="flex items-center space-x-2">
            <span
              className={`w-1.5 h-1.5 rounded-full flex-shrink-0 ${
                isTampered ? 'bg-red-400 animate-ping' : SEVERITY_DOT[entry.severity] ?? 'bg-slate-400'
              }`}
            />
            <span className="text-sm font-mono text-slate-300">#{entry.sequence_id}</span>
            {isTampered && (
              <span className="text-[10px] font-mono font-bold bg-red-500/30 text-red-200 border border-red-500/50 px-1.5 py-0.5 rounded animate-pulse">
                TAMPERED
              </span>
            )}
          </div>
        </td>

        {/* Hash */}
        <td className="px-4 py-3 whitespace-nowrap">
          <div className="flex items-center space-x-1 text-xs font-mono text-violet-400/80">
            <span className="text-slate-600">{truncateHash(entry.previous_hash, 6)}</span>
            <ArrowRight className="w-3 h-3 text-slate-700" />
            <span
              className={`px-1.5 py-0.5 rounded border ${
                isTampered
                  ? 'bg-red-500/20 border-red-500/40 text-red-300 font-semibold'
                  : 'bg-violet-500/5 border-violet-500/15'
              }`}
            >
              {truncateHash(entry.entry_hash)}
            </span>
          </div>
        </td>

        {/* Action */}
        <td className="px-4 py-3 whitespace-nowrap">
          <span
            className={`inline-flex px-2 py-0.5 rounded-md text-[11px] font-bold uppercase tracking-wide border ${
              ACTION_STYLE[entry.action] ?? ''
            }`}
          >
            {entry.action}
          </span>
        </td>

        {/* Table */}
        <td className="px-4 py-3 whitespace-nowrap text-xs font-mono text-slate-400">
          {entry.table_name}
        </td>

        {/* Actor */}
        <td className="px-4 py-3 whitespace-nowrap">
          <div className="flex items-center space-x-2">
            <div className="w-5 h-5 rounded-full bg-indigo-500/20 border border-indigo-500/30 flex items-center justify-center text-[9px] font-bold text-indigo-300 uppercase">
              {entry.actor_name.charAt(0)}
            </div>
            <span className="text-xs text-slate-400 max-w-[140px] truncate">{entry.actor_name}</span>
          </div>
        </td>

        {/* Severity */}
        <td className="px-4 py-3 whitespace-nowrap">
          <span
            className={`inline-flex px-2 py-0.5 rounded-md text-[10px] font-semibold uppercase tracking-wide border ${
              SEVERITY_STYLE[entry.severity] ?? ''
            }`}
          >
            {entry.severity}
          </span>
        </td>

        {/* When */}
        <td className="px-4 py-3 whitespace-nowrap text-xs text-slate-500">
          {relativeTime(entry.created_at)}
        </td>

        {/* Expand */}
        <td className="px-4 py-3 text-right">
          <span className="text-slate-600 group-hover:text-slate-400 transition-colors">
            {open ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
          </span>
        </td>
      </tr>

      {/* Diff drawer */}
      {open && (
        <tr>
          <td colSpan={8} className="p-0">
            <div className="px-6 py-4 bg-slate-900/70 border-t border-slate-700/50 space-y-4">
              <DiffViewer
                oldValue={entry.old_value}
                newValue={entry.new_value}
                operation={entry.action}
              />
              <div className="flex items-center justify-end space-x-2 pt-2 border-t border-slate-800">
                <button
                  type="button"
                  onClick={(e) => {
                    e.stopPropagation();
                    navigate(`/auditor/chain?seq=${entry.sequence_id}`);
                  }}
                  className="px-3 py-1.5 rounded-lg bg-violet-600/20 hover:bg-violet-600/30 border border-violet-500/30 text-violet-200 text-xs font-medium flex items-center space-x-1.5 transition-colors"
                >
                  <GitBranch className="w-3.5 h-3.5 text-violet-400" />
                  <span>Inspect in Chain Explorer</span>
                </button>
                <button
                  type="button"
                  onClick={(e) => {
                    e.stopPropagation();
                    const empId = entry.employee_id || entry.row_id;
                    navigate(`/auditor/time-travel?emp_id=${empId}&as_of=${encodeURIComponent(entry.created_at)}`);
                  }}
                  className="px-3 py-1.5 rounded-lg bg-indigo-600/20 hover:bg-indigo-600/30 border border-indigo-500/30 text-indigo-200 text-xs font-medium flex items-center space-x-1.5 transition-colors"
                >
                  <Clock className="w-3.5 h-3.5 text-indigo-400" />
                  <span>Time-Travel to Change ⏱</span>
                </button>
              </div>
            </div>
          </td>
        </tr>
      )}
    </>
  );
}

// ─── Filter bar ───────────────────────────────────────────────────────────────

interface FilterBarProps {
  filters: AuditLogFilters;
  onChange: (f: Partial<AuditLogFilters>) => void;
}

function FilterBar({ filters, onChange }: FilterBarProps) {
  return (
    <div className="flex flex-wrap items-center gap-3 px-5 py-3.5 border-b border-slate-700/50 bg-slate-900/30">
      <SlidersHorizontal className="w-4 h-4 text-violet-400 flex-shrink-0" />

      {/* Table name search */}
      <div className="relative">
        <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-slate-500" />
        <input
          type="text"
          placeholder="Table name…"
          value={filters.table_name ?? ''}
          onChange={(e) => onChange({ table_name: e.target.value, page: 1 })}
          className="pl-8 pr-3 py-1.5 bg-slate-800 border border-slate-700 rounded-lg text-xs text-slate-300 placeholder-slate-600 focus:outline-none focus:ring-1 focus:ring-violet-500/50 focus:border-violet-500/50 w-36 transition-all"
        />
      </div>

      {/* Sequence ID search */}
      <div className="relative">
        <Hash className="absolute left-2.5 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-slate-500" />
        <input
          type="number"
          placeholder="Seq #…"
          value={filters.sequence_id ?? ''}
          onChange={(e) => {
            const val = e.target.value ? parseInt(e.target.value, 10) : undefined;
            onChange({ sequence_id: val, page: 1 });
          }}
          className="pl-8 pr-3 py-1.5 bg-slate-800 border border-slate-700 rounded-lg text-xs text-slate-300 placeholder-slate-600 focus:outline-none focus:ring-1 focus:ring-violet-500/50 focus:border-violet-500/50 w-24 transition-all font-mono"
        />
      </div>

      {/* Encrypted National ID Blind Search (BLIND-003) */}
      <div className="relative">
        <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-slate-500" />
        <input
          type="text"
          placeholder="Search National ID (Blind Index)…"
          value={filters.national_id_search ?? ''}
          onChange={(e) => onChange({ national_id_search: e.target.value, page: 1 })}
          className="pl-8 pr-3 py-1.5 bg-slate-800 border border-slate-700 rounded-lg text-xs text-slate-300 placeholder-slate-600 focus:outline-none focus:ring-1 focus:ring-violet-500/50 focus:border-violet-500/50 w-56 transition-all font-mono"
        />
      </div>

      {/* Action filter */}
      <select
        value={filters.action ?? ''}
        onChange={(e) => onChange({ action: e.target.value as AuditLogFilters['action'], page: 1 })}
        className="px-3 py-1.5 bg-slate-800 border border-slate-700 rounded-lg text-xs text-slate-300 focus:outline-none focus:ring-1 focus:ring-violet-500/50"
      >
        <option value="">All actions</option>
        <option value="INSERT">INSERT</option>
        <option value="UPDATE">UPDATE</option>
        <option value="DELETE">DELETE</option>
      </select>

      {/* Severity filter */}
      <select
        value={filters.severity ?? ''}
        onChange={(e) => onChange({ severity: e.target.value as AuditLogFilters['severity'], page: 1 })}
        className="px-3 py-1.5 bg-slate-800 border border-slate-700 rounded-lg text-xs text-slate-300 focus:outline-none focus:ring-1 focus:ring-violet-500/50"
      >
        <option value="">All severities</option>
        <option value="INFO">INFO</option>
        <option value="WARNING">WARNING</option>
        <option value="CRITICAL">CRITICAL</option>
      </select>

      {/* Clear */}
      {(filters.table_name || filters.action || filters.severity || filters.national_id_search || filters.sequence_id !== undefined) && (
        <button
          onClick={() => onChange({ table_name: '', action: '', severity: '', national_id_search: '', sequence_id: undefined, page: 1 })}
          className="text-xs text-slate-500 hover:text-slate-300 transition-colors underline underline-offset-2"
        >
          Clear filters
        </button>
      )}
    </div>
  );
}

// ─── Main component ───────────────────────────────────────────────────────────

export default function AuditLogTable() {
  const { getToken } = useAuth();
  const [searchParams, setSearchParams] = useSearchParams();
  const seqParam = searchParams.get('seq');
  const targetSeq = seqParam ? parseInt(seqParam, 10) : undefined;
  const incident = useIncidentStatus();

  const [filters, setFilters] = useState<AuditLogFilters>({
    page: 1,
    limit: 20,
    sequence_id: targetSeq && !isNaN(targetSeq) ? targetSeq : undefined,
  });

  useEffect(() => {
    if (seqParam) {
      const parsed = parseInt(seqParam, 10);
      if (!isNaN(parsed) && filters.sequence_id !== parsed) {
        setFilters((prev) => ({ ...prev, sequence_id: parsed, page: 1 }));
      }
    }
  }, [seqParam]);

  const { data, isLoading, isError, isFetching } = useQuery({
    queryKey: ['auditLogs', filters],
    queryFn: () => fetchAuditLogs(filters, getToken),
    refetchInterval: 10000,
  });

  const updateFilters = (patch: Partial<AuditLogFilters>) => {
    if (patch.sequence_id === undefined && searchParams.has('seq')) {
      searchParams.delete('seq');
      setSearchParams(searchParams);
    }
    setFilters((prev) => ({ ...prev, ...patch }));
  };

  const page  = filters.page  ?? 1;
  const limit = filters.limit ?? 20;

  return (
    <div className="bg-slate-900/50 border border-slate-700/50 rounded-2xl overflow-hidden">
      {/* Header */}
      <div className="flex items-center justify-between px-5 py-4 border-b border-slate-700/50">
        <div className="flex items-center space-x-3">
          <Hash className="w-5 h-5 text-violet-400" />
          <h3 className="text-sm font-semibold text-slate-200">Audit Log</h3>
          {data && (
            <span className="text-xs text-slate-500 bg-slate-800 px-2 py-0.5 rounded border border-slate-700">
              {data.total.toLocaleString()} entries
            </span>
          )}
          {filters.sequence_id !== undefined && (
            <span className="text-xs font-mono font-semibold bg-violet-500/20 text-violet-300 border border-violet-500/30 px-2 py-0.5 rounded">
              Seq #{filters.sequence_id}
            </span>
          )}
          {isFetching && !isLoading && (
            <span className="text-[10px] text-violet-400 animate-pulse">refreshing…</span>
          )}
        </div>
        <span className="text-xs text-slate-600 italic">Click any row to expand diff</span>
      </div>

      {/* Filters */}
      <FilterBar filters={filters} onChange={updateFilters} />

      {/* Table */}
      <div className="overflow-x-auto">
        <table className="min-w-full">
          <thead className="bg-slate-900/60">
            <tr>
              {['Entry', 'Hash', 'Action', 'Table', 'Actor', 'Severity', 'When', ''].map((h) => (
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
            {isLoading ? (
              <tr>
                <td colSpan={8} className="px-6 py-16 text-center">
                  <div className="flex flex-col items-center space-y-3 text-slate-500">
                    <div className="w-6 h-6 border-2 border-violet-500/30 border-t-violet-400 rounded-full animate-spin" />
                    <span className="text-sm">Loading audit log…</span>
                  </div>
                </td>
              </tr>
            ) : isError ? (
              <tr>
                <td colSpan={8} className="px-6 py-12 text-center text-red-400 text-sm">
                  Failed to load audit log. Check the network tab.
                </td>
              </tr>
            ) : data?.items.length === 0 ? (
              <tr>
                <td colSpan={8} className="px-6 py-16 text-center">
                  <div className="flex flex-col items-center space-y-2 text-slate-600">
                    <Hash className="w-8 h-8 text-slate-700" />
                    <p className="text-sm">No audit log entries yet.</p>
                    <p className="text-xs">Entries will appear once Abhinav's triggers land and HR actions are performed.</p>
                  </div>
                </td>
              </tr>
            ) : (
              data?.items.map((entry) => (
                <AuditRow
                  key={entry.sequence_id}
                  entry={entry}
                  isTampered={entry.sequence_id === incident.tamperedSeqId}
                  isTargetSeq={entry.sequence_id === targetSeq}
                />
              ))
            )}
          </tbody>
        </table>
      </div>

      {/* Pagination */}
      {data && data.pages > 1 && (
        <div className="px-5 py-3.5 border-t border-slate-700/50 flex items-center justify-between bg-slate-900/30">
          <p className="text-xs text-slate-500 font-mono">
            {((page - 1) * limit) + 1}–{Math.min(page * limit, data.total)} of {data.total.toLocaleString()}
          </p>
          <div className="flex items-center space-x-1">
            <button
              onClick={() => updateFilters({ page: page - 1 })}
              disabled={page === 1}
              className="p-1.5 rounded-lg border border-slate-700 text-slate-400 hover:text-slate-200 hover:border-slate-600 disabled:opacity-30 disabled:cursor-not-allowed transition-all"
            >
              <ChevronLeft className="w-4 h-4" />
            </button>
            <span className="text-xs text-slate-500 px-2 font-mono">
              {page} / {data.pages}
            </span>
            <button
              onClick={() => updateFilters({ page: page + 1 })}
              disabled={page === data.pages}
              className="p-1.5 rounded-lg border border-slate-700 text-slate-400 hover:text-slate-200 hover:border-slate-600 disabled:opacity-30 disabled:cursor-not-allowed transition-all"
            >
              <ChevronRight className="w-4 h-4" />
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
