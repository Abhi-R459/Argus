import React, { useState, useRef } from 'react';
import { useSearchParams, useNavigate } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { useAuth } from '@clerk/clerk-react';
import {
  ChevronLeft, ChevronRight, Search,
  Hash, ChevronDown, ChevronUp, ArrowRight, GitBranch, Clock,
  Filter, Check
} from 'lucide-react';
import {
  fetchAuditLogs,
  useIncidentStatus,
  type AuditLogFilters,
  type AuditLogItem,
} from '../../services/auditService';
import DiffViewer from './DiffViewer';
import RefreshButton from '../common/RefreshButton';
import { DataTable } from '../common/DataTable';
import { FilterBar, type ActiveFilterItem } from '../common/FilterBar';
import { Button } from '../common/Button';
import { SkeletonRows } from '../common/SkeletonRows';
import { useKeyboardNav } from '../../hooks/useKeyboardNav';

// ─── Badges & styles ─────────────────────────────────────────────────────────

const ACTION_STYLE: Record<string, string> = {
  INSERT: 'bg-linear-success/15 text-linear-success border-linear-success/30',
  UPDATE: 'bg-linear-primary/15 text-linear-primary border-linear-primary/30',
  DELETE: 'bg-grafana-orange/15 text-grafana-orange border-grafana-orange/30',
};

const SEVERITY_STYLE: Record<string, string> = {
  INFO:     'bg-linear-surface-2 text-linear-ink-muted border-linear-hairline',
  WARNING:  'bg-grafana-orange/15 text-grafana-orange border-grafana-orange/30',
  CRITICAL: 'bg-grafana-orange/20 text-grafana-orange border-grafana-orange/40 font-semibold',
};

const SEVERITY_DOT: Record<string, string> = {
  INFO:     'bg-linear-ink-subtle',
  WARNING:  'bg-linear-primary',
  CRITICAL: 'bg-grafana-orange',
};

function truncateHash(h: string, n = 8) {
  return h.length <= n + 3 ? h : `${h.slice(0, n)}…`;
}

function relativeTime(iso: string) {
  const diff = Math.max(0, Date.now() - new Date(iso).getTime());
  const s = Math.floor(diff / 1000);
  if (s < 5) return 'just now';
  if (s < 60) return `${s}s ago`;
  const m = Math.floor(s / 60);
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
  isSelected,
  isOpen,
  onToggleOpen,
}: {
  entry: AuditLogItem;
  isTampered?: boolean;
  isTargetSeq?: boolean;
  isSelected?: boolean;
  isOpen: boolean;
  onToggleOpen: () => void;
}) {
  const [copied, setCopied] = useState(false);
  const navigate = useNavigate();

  const handleCopyHash = (e: React.MouseEvent) => {
    e.stopPropagation();
    navigator.clipboard.writeText(entry.entry_hash);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <>
      <DataTable.Row
        isSelected={isSelected || isTargetSeq}
        isTampered={isTampered}
        portalTheme="auditor"
        onClick={onToggleOpen}
        className={isOpen ? 'bg-linear-surface-2' : ''}
      >
        {/* Seq ID */}
        <DataTable.Cell tabularNums mono className="font-bold">
          <div className="flex items-center space-x-1.5">
            <span
              className={`w-1.5 h-1.5 rounded-full flex-shrink-0 ${
                isTampered ? 'bg-grafana-orange' : SEVERITY_DOT[entry.severity] ?? 'bg-linear-ink-subtle'
              }`}
            />
            <span className={isTampered ? 'text-grafana-orange' : 'text-linear-ink'}>
              #{entry.sequence_id}
            </span>
            {isTampered && (
              <span className="text-[10px] font-mono font-bold bg-grafana-orange/20 text-grafana-orange border border-grafana-orange/40 px-1 py-0.2 rounded">
                TAMPERED
              </span>
            )}
          </div>
        </DataTable.Cell>

        {/* Action */}
        <DataTable.Cell>
          <span
            className={`inline-flex px-1.5 py-0.5 rounded text-[10px] font-mono font-bold uppercase tracking-wide border ${
              ACTION_STYLE[entry.action] ?? ''
            }`}
          >
            {entry.action}
          </span>
        </DataTable.Cell>

        {/* Table */}
        <DataTable.Cell mono className="text-linear-ink-muted">
          {entry.table_name}
        </DataTable.Cell>

        {/* Actor */}
        <DataTable.Cell className="text-linear-ink max-w-[130px] truncate">
          <div className="flex items-center space-x-1.5">
            <div className="w-4 h-4 rounded-full bg-linear-surface-3 border border-linear-hairline flex items-center justify-center text-[8px] font-bold text-linear-primary uppercase">
              {entry.actor_name.charAt(0)}
            </div>
            <span className="truncate">{entry.actor_name}</span>
          </div>
        </DataTable.Cell>

        {/* Hash Linkage */}
        <DataTable.Cell mono>
          <div className="flex items-center space-x-1 text-xs text-linear-primary">
            <span className="text-linear-ink-subtle">{truncateHash(entry.previous_hash, 6)}</span>
            <ArrowRight className="w-2.5 h-2.5 text-linear-ink-muted" />
            <Button
              type="button"
              variant="ghost"
              size="xs"
              portalTheme="auditor"
              onClick={handleCopyHash}
              title="Click to copy full entry hash"
              aria-label="Copy full entry hash"
              className="px-1.5 py-0.5 text-[11px] font-mono text-linear-primary hover:bg-linear-surface-3"
            >
              <span>{truncateHash(entry.entry_hash, 6)}</span>
              {copied && <Check className="w-3 h-3 text-linear-success inline ml-1" />}
            </Button>
          </div>
        </DataTable.Cell>

        {/* Severity */}
        <DataTable.Cell>
          <span
            className={`inline-flex px-1.5 py-0.5 rounded text-[10px] font-semibold uppercase tracking-wide border ${
              SEVERITY_STYLE[entry.severity] ?? ''
            }`}
          >
            {entry.severity}
          </span>
        </DataTable.Cell>

        {/* Recorded When */}
        <DataTable.Cell align="right" mono className="text-linear-ink-muted text-[11px]">
          <span title={new Date(entry.created_at).toLocaleString()}>
            {relativeTime(entry.created_at)}
          </span>
        </DataTable.Cell>

        {/* Expand Indicator */}
        <DataTable.Cell align="center" className="w-8">
          <span className="text-linear-ink-subtle">
            {isOpen ? <ChevronUp className="w-3.5 h-3.5" /> : <ChevronDown className="w-3.5 h-3.5" />}
          </span>
        </DataTable.Cell>
      </DataTable.Row>

      {/* Diff drawer accordion */}
      {isOpen && (
        <tr>
          <td colSpan={8} className="p-0 border-b border-linear-hairline">
            <div className="px-5 py-3.5 bg-linear-canvas space-y-3">
              <DiffViewer
                oldValue={entry.old_value}
                newValue={entry.new_value}
                operation={entry.action}
              />
              <div className="flex items-center justify-end space-x-2 pt-2 border-t border-linear-hairline/60">
                <Button
                  type="button"
                  variant="secondary"
                  size="sm"
                  portalTheme="auditor"
                  onClick={(e) => {
                    e.stopPropagation();
                    navigate(`/auditor/chain?seq=${entry.sequence_id}`);
                  }}
                  leftIcon={<GitBranch className="w-3.5 h-3.5 text-linear-primary" />}
                >
                  Inspect in Chain Explorer
                </Button>
                <Button
                  type="button"
                  variant="secondary"
                  size="sm"
                  portalTheme="auditor"
                  onClick={(e) => {
                    e.stopPropagation();
                    const empId = entry.employee_id || entry.row_id;
                    navigate(`/auditor/time-travel?emp_id=${empId}&as_of=${encodeURIComponent(entry.created_at)}`);
                  }}
                  leftIcon={<Clock className="w-3.5 h-3.5 text-linear-primary" />}
                >
                  Time-Travel to Change ⏱
                </Button>
              </div>
            </div>
          </td>
        </tr>
      )}
    </>
  );
}

// ─── Main AuditLogTable component ──────────────────────────────────────────────

export default function AuditLogTable() {
  const { getToken } = useAuth();
  const [searchParams] = useSearchParams();
  const incident = useIncidentStatus();

  const searchInputRef = useRef<HTMLInputElement>(null);

  // Pre-seed sequence_id filter if ?seq= is passed
  const targetSeqParam = searchParams.get('seq');
  const targetSeqId = targetSeqParam ? parseInt(targetSeqParam, 10) : undefined;

  const [filters, setFilters] = useState<AuditLogFilters>({
    page: 1,
    limit: 25,
    sequence_id: targetSeqId,
  });

  const [focusedRowIndex, setFocusedRowIndex] = useState<number>(0);
  const [openRowSeq, setOpenRowSeq] = useState<number | null>(targetSeqId ?? null);

  const {
    data,
    isLoading,
    isFetching,
    refetch,
  } = useQuery({
    queryKey: ['audit-logs', filters],
    queryFn: () => fetchAuditLogs(filters, getToken),
    placeholderData: (prev) => prev,
    refetchInterval: 3000,
  });

  const items = data?.items ?? [];
  const total = data?.total ?? 0;
  const totalPages = data?.pages ?? Math.ceil(total / (filters.limit ?? 25));

  const handleFilterChange = (patch: Partial<AuditLogFilters>) => {
    setFilters((prev) => ({ ...prev, ...patch }));
  };

  // Active filter items for FilterBar
  const activeFilters: ActiveFilterItem[] = [];
  if (filters.table_name) {
    activeFilters.push({
      id: 'table',
      label: 'Table',
      value: filters.table_name,
      onRemove: () => handleFilterChange({ table_name: undefined, page: 1 }),
    });
  }
  if (filters.sequence_id !== undefined) {
    activeFilters.push({
      id: 'seq',
      label: 'Seq #',
      value: String(filters.sequence_id),
      onRemove: () => handleFilterChange({ sequence_id: undefined, page: 1 }),
    });
  }
  if (filters.action) {
    activeFilters.push({
      id: 'action',
      label: 'Action',
      value: filters.action,
      onRemove: () => handleFilterChange({ action: undefined, page: 1 }),
    });
  }
  if (filters.severity) {
    activeFilters.push({
      id: 'severity',
      label: 'Severity',
      value: filters.severity,
      onRemove: () => handleFilterChange({ severity: undefined, page: 1 }),
    });
  }
  if (filters.national_id_search) {
    activeFilters.push({
      id: 'nid',
      label: 'National ID (Blind)',
      value: filters.national_id_search,
      onRemove: () => handleFilterChange({ national_id_search: undefined, page: 1 }),
    });
  }

  const handleClearAll = () => {
    setFilters({ page: 1, limit: 25 });
  };

  // Keyboard navigation
  useKeyboardNav({
    itemCount: items.length,
    selectedIndex: focusedRowIndex,
    onSelectIndex: (idx) => setFocusedRowIndex(idx),
    onPeek: (idx) => {
      const entry = items[idx];
      if (entry) {
        setOpenRowSeq((curr) => (curr === entry.sequence_id ? null : entry.sequence_id));
      }
    },
    onDismiss: () => setOpenRowSeq(null),
    searchInputRef,
    enabled: true,
  });

  return (
    <div className="space-y-3">
      {/* Faceted Filter Toolbar */}
      <FilterBar activeFilters={activeFilters} onClearAll={handleClearAll} portalTheme="auditor">
        <div className="flex flex-wrap items-center gap-2.5 flex-1">
          {/* Table name */}
          <div className="relative">
            <Search className="w-3.5 h-3.5 text-linear-ink-subtle absolute left-2.5 top-1/2 -translate-y-1/2 pointer-events-none" />
            <input
              ref={searchInputRef}
              type="text"
              placeholder="Filter table (/)..."
              value={filters.table_name ?? ''}
              onChange={(e) => handleFilterChange({ table_name: e.target.value || undefined, page: 1 })}
              className="pl-8 pr-2.5 py-1.5 bg-linear-canvas border border-linear-hairline rounded-lg text-xs text-linear-ink placeholder-linear-ink-subtle focus:outline-none focus:border-linear-primary w-36 font-mono"
            />
          </div>

          {/* Sequence ID */}
          <div className="relative">
            <Hash className="w-3.5 h-3.5 text-linear-ink-subtle absolute left-2.5 top-1/2 -translate-y-1/2 pointer-events-none" />
            <input
              type="number"
              placeholder="Seq #..."
              value={filters.sequence_id ?? ''}
              onChange={(e) => {
                const val = e.target.value ? parseInt(e.target.value, 10) : undefined;
                handleFilterChange({ sequence_id: val, page: 1 });
              }}
              className="pl-8 pr-2.5 py-1.5 bg-linear-canvas border border-linear-hairline rounded-lg text-xs text-linear-ink placeholder-linear-ink-subtle focus:outline-none focus:border-linear-primary w-24 font-mono"
            />
          </div>

          {/* Encrypted National ID Blind Search */}
          <div className="relative">
            <Search className="w-3.5 h-3.5 text-linear-ink-subtle absolute left-2.5 top-1/2 -translate-y-1/2 pointer-events-none" />
            <input
              type="text"
              placeholder="Blind National ID search..."
              value={filters.national_id_search ?? ''}
              onChange={(e) => handleFilterChange({ national_id_search: e.target.value || undefined, page: 1 })}
              className="pl-8 pr-2.5 py-1.5 bg-linear-canvas border border-linear-hairline rounded-lg text-xs text-linear-ink placeholder-linear-ink-subtle focus:outline-none focus:border-linear-primary w-48 font-mono"
            />
          </div>

          {/* Action filter */}
          <div className="flex items-center space-x-1">
            <Filter className="w-3 h-3 text-linear-ink-muted" />
            <select
              value={filters.action ?? ''}
              onChange={(e) => handleFilterChange({ action: (e.target.value || undefined) as any, page: 1 })}
              className="bg-linear-canvas border border-linear-hairline rounded-lg px-2.5 py-1.5 text-xs text-linear-ink focus:outline-none focus:border-linear-primary font-mono"
            >
              <option value="">All Actions</option>
              <option value="INSERT">INSERT</option>
              <option value="UPDATE">UPDATE</option>
              <option value="DELETE">DELETE</option>
            </select>
          </div>

          {/* Severity filter */}
          <select
            value={filters.severity ?? ''}
            onChange={(e) => handleFilterChange({ severity: (e.target.value || undefined) as any, page: 1 })}
            className="bg-linear-canvas border border-linear-hairline rounded-lg px-2.5 py-1.5 text-xs text-linear-ink focus:outline-none focus:border-linear-primary font-mono"
          >
            <option value="">All Severities</option>
            <option value="INFO">INFO</option>
            <option value="WARNING">WARNING</option>
            <option value="CRITICAL">CRITICAL</option>
          </select>
        </div>

        {/* Sync button */}
        <RefreshButton
          onRefresh={() => refetch()}
          label="Sync"
          variant="dark"
          title="Refresh audit logs"
          className="px-2.5 py-1 rounded-lg text-xs"
        />
      </FilterBar>

      {/* Dense Compound DataTable */}
      <DataTable.Root portalTheme="auditor">
        <DataTable.Header portalTheme="auditor">
          <tr>
            <DataTable.HeadCell className="w-20">Seq #</DataTable.HeadCell>
            <DataTable.HeadCell className="w-20">Action</DataTable.HeadCell>
            <DataTable.HeadCell className="w-28">Table</DataTable.HeadCell>
            <DataTable.HeadCell>Actor</DataTable.HeadCell>
            <DataTable.HeadCell>Hash Linkage</DataTable.HeadCell>
            <DataTable.HeadCell className="w-20">Severity</DataTable.HeadCell>
            <DataTable.HeadCell align="right">When</DataTable.HeadCell>
            <DataTable.HeadCell className="w-8">{''}</DataTable.HeadCell>
          </tr>
        </DataTable.Header>

        {isLoading ? (
          <SkeletonRows rowCount={12} columnCount={8} portalTheme="auditor" />
        ) : items.length === 0 ? (
          <tbody>
            <tr>
              <td colSpan={8} className="py-12 text-center text-xs text-linear-ink-muted">
                <Hash className="w-6 h-6 mx-auto mb-2 text-linear-ink-subtle" />
                <p className="font-medium text-linear-ink">No audit entries matching filters</p>
                <p className="text-linear-ink-subtle text-[11px] mt-0.5">
                  Try clearing active filter chips or adjusting query parameters.
                </p>
              </td>
            </tr>
          </tbody>
        ) : (
          <DataTable.Body portalTheme="auditor">
            {items.map((entry, idx) => (
              <AuditRow
                key={entry.sequence_id}
                entry={entry}
                isTampered={incident.tamperedSeqId === entry.sequence_id}
                isTargetSeq={targetSeqId === entry.sequence_id}
                isSelected={focusedRowIndex === idx}
                isOpen={openRowSeq === entry.sequence_id}
                onToggleOpen={() => {
                  setFocusedRowIndex(idx);
                  setOpenRowSeq((curr) => (curr === entry.sequence_id ? null : entry.sequence_id));
                }}
              />
            ))}
          </DataTable.Body>
        )}
      </DataTable.Root>

      {/* Pagination Bar */}
      {totalPages > 1 && (
        <div className="flex items-center justify-between px-1 py-1 text-xs">
          <Button
            type="button"
            variant="secondary"
            size="sm"
            portalTheme="auditor"
            onClick={() => handleFilterChange({ page: Math.max(1, (filters.page ?? 1) - 1) })}
            disabled={(filters.page ?? 1) <= 1 || isFetching}
            leftIcon={<ChevronLeft className="w-3 h-3" />}
          >
            Previous
          </Button>

          <div className="text-linear-ink-muted font-mono text-[11px]">
            Page {filters.page ?? 1} of {totalPages} ({total} entries)
            <span className="ml-2 text-linear-ink-subtle">(Use J/K to navigate, Space to peek)</span>
          </div>

          <Button
            type="button"
            variant="secondary"
            size="sm"
            portalTheme="auditor"
            onClick={() => handleFilterChange({ page: Math.min(totalPages, (filters.page ?? 1) + 1) })}
            disabled={(filters.page ?? 1) >= totalPages || isFetching}
            rightIcon={<ChevronRight className="w-3 h-3" />}
          >
            Next
          </Button>
        </div>
      )}
    </div>
  );
}
