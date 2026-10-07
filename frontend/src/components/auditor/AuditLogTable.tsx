import React, { useState, useRef, useEffect } from 'react';
import { useSearchParams, useNavigate } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { useAuth } from '@clerk/clerk-react';
import {
  ChevronLeft, ChevronRight, Search,
  Hash, ChevronDown, ArrowRight, GitBranch, Clock,
  Filter
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
import { EmptyState } from '../common/EmptyState';
import { CopyButton } from '../common/CopyButton';
import { useKeyboardNav } from '../../hooks/useKeyboardNav';
import { useAccordionTransition } from '../../hooks/useAccordionTransition';
import { formatRelativeTime, truncateHash } from '../../lib/format';
import { getActionSemantic, getSeverityDotClass, getSeverityChipClass } from '../../lib/semantics';

// ─── Expandable row ───────────────────────────────────────────────────────────

const AuditRow = React.forwardRef<
  HTMLTableRowElement,
  {
    entry: AuditLogItem;
    isTampered?: boolean;
    tamperDetails?: string | null;
    isTargetSeq?: boolean;
    isSelected?: boolean;
    isFocused?: boolean;
    isOpen: boolean;
    onToggleOpen: () => void;
  }
>(
  (
    {
      entry,
      isTampered,
      tamperDetails,
      isTargetSeq,
      isSelected,
      isFocused,
      isOpen,
      onToggleOpen,
    },
    ref
  ) => {
    const navigate = useNavigate();
    const actionSemantic = getActionSemantic(entry.action, entry.table_name, 'auditor');
    const { isRendered, isExpanded } = useAccordionTransition(isOpen);

    return (
      <>
        <DataTable.Row
          ref={ref}
          isSelected={isSelected}
          isHighlighted={isTargetSeq}
          isFocused={isFocused}
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
                isTampered ? 'bg-status-warning' : getSeverityDotClass(entry.severity)
              }`}
            />
            <span className={isTampered ? 'text-status-warning' : 'text-linear-ink'}>
              #{entry.sequence_id}
            </span>
            {isTampered && (
              <span className="text-[10px] font-mono font-bold bg-status-warning/20 text-status-warning border border-status-warning/40 px-1 py-0.5 rounded">
                TAMPERED
              </span>
            )}
          </div>
        </DataTable.Cell>

        {/* Action */}
        <DataTable.Cell>
          <span
            className={`inline-flex px-1.5 py-0.5 rounded text-[10px] font-mono font-bold uppercase tracking-wide border ${
              actionSemantic.className
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
            <span className="truncate" title={entry.actor_user_id === null ? 'No immutable actor user ID recorded' : `Current profile for immutable user ID ${entry.actor_user_id}`}>
              {entry.actor_user_id === null
                ? `${entry.actor_name} · no user ID`
                : `${entry.actor_name} · user #${entry.actor_user_id}`}
            </span>
          </div>
        </DataTable.Cell>

        {/* Hash Linkage */}
        <DataTable.Cell mono>
          <div className="flex items-center space-x-1 text-xs text-linear-primary">
            <span className="text-linear-ink-subtle">{truncateHash(entry.previous_hash, 6)}</span>
            <ArrowRight className="w-2.5 h-2.5 text-linear-ink-muted" />
            <CopyButton
              text={entry.entry_hash}
              label={truncateHash(entry.entry_hash, 6)}
              portalTheme="auditor"
              title="Click to copy full entry hash"
            />
          </div>
        </DataTable.Cell>

        {/* Severity */}
        <DataTable.Cell>
          <span
            className={`inline-flex px-1.5 py-0.5 rounded text-[10px] uppercase tracking-wide border ${
              getSeverityChipClass(entry.severity, 'auditor')
            }`}
          >
            {entry.severity}
          </span>
        </DataTable.Cell>

        {/* Recorded When */}
        <DataTable.Cell align="right" mono className="text-linear-ink-muted text-[11px]">
          <span title={new Date(entry.created_at).toLocaleString()}>
            {formatRelativeTime(entry.created_at)}
          </span>
        </DataTable.Cell>

        {/* Expand Indicator with smooth 180-deg chevron rotation */}
        <DataTable.Cell align="center" className="w-8">
          <span
            className={`inline-flex items-center justify-center text-linear-ink-subtle transition-transform duration-280 ease-out ${
              isOpen ? 'rotate-180 text-linear-ink' : 'rotate-0'
            }`}
          >
            <ChevronDown className="w-3.5 h-3.5" />
          </span>
        </DataTable.Cell>
      </DataTable.Row>

      {/* Diff drawer accordion with smooth slide down / slide up */}
      {isRendered && (
        <tr>
          <td colSpan={8} className="p-0 border-b border-linear-hairline">
            <div
              className={`accordion-collapse ${isExpanded ? 'accordion-open' : ''}`}
            >
              <div className="accordion-collapse-inner">
                <div className="px-5 py-3.5 bg-linear-canvas space-y-3">
                  <DiffViewer
                    oldValue={entry.old_value}
                    newValue={entry.new_value}
                    operation={entry.action}
                    isTampered={isTampered}
                    tamperDetails={tamperDetails}
                    sequenceId={entry.sequence_id}
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
              </div>
            </div>
          </td>
        </tr>
      )}
      </>
    );
  }
);
AuditRow.displayName = 'AuditRow';

// ─── Main AuditLogTable component ──────────────────────────────────────────────

export default function AuditLogTable() {
  const { getToken } = useAuth();
  const [searchParams] = useSearchParams();
  const incident = useIncidentStatus();

  const searchInputRef = useRef<HTMLInputElement>(null);
  const rowRefs = useRef<(HTMLTableRowElement | null)[]>([]);

  // Pre-seed sequence_id filter if ?seq= is passed
  const targetSeqParam = searchParams.get('seq');
  const targetSeqId = targetSeqParam ? parseInt(targetSeqParam, 10) : undefined;

  const [filters, setFilters] = useState<AuditLogFilters>({
    page: 1,
    limit: 25,
    sequence_id: targetSeqId,
  });
  const [cursorByPage, setCursorByPage] = useState<Record<number, number>>({});

  const [focusedRowIndex, setFocusedRowIndex] = useState<number>(-1);
  const [openRowSeq, setOpenRowSeq] = useState<number | null>(targetSeqId ?? null);

  const {
    data,
    isLoading,
    isFetching,
    refetch,
  } = useQuery({
    queryKey: ['audit-logs', filters],
    queryFn: () => fetchAuditLogs({
      ...filters,
      before_sequence_id: cursorByPage[filters.page ?? 1],
    }, getToken),
    placeholderData: (prev) => prev,
  });

  const items = data?.items ?? [];
  const total = data?.total ?? 0;
  const totalPages = data?.pages ?? Math.ceil(total / (filters.limit ?? 25));

  // Auto-scroll focused row into view when focusedRowIndex changes
  useEffect(() => {
    const rowEl = rowRefs.current[focusedRowIndex];
    if (rowEl) {
      rowEl.scrollIntoView({ block: 'nearest', behavior: 'smooth' });
    }
  }, [focusedRowIndex]);

  // Keep rowRefs aligned with items
  useEffect(() => {
    rowRefs.current = rowRefs.current.slice(0, items.length);
    if (items.length > 0 && focusedRowIndex >= items.length) {
      setFocusedRowIndex(-1);
    }
  }, [items.length, focusedRowIndex]);

  const handleFilterChange = (patch: Partial<AuditLogFilters>) => {
    if (Object.keys(patch).some((key) => key !== 'page')) {
      setCursorByPage({});
    }
    setFilters((prev) => ({ ...prev, ...patch }));
  };

  const goToNextPage = () => {
    const nextPage = (filters.page ?? 1) + 1;
    if (data?.next_cursor) {
      setCursorByPage((previous) => ({ ...previous, [nextPage]: data.next_cursor! }));
    }
    handleFilterChange({ page: Math.min(totalPages, nextPage) });
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
    setCursorByPage({});
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
              id="audit-log-table-filter"
              name="table_name"
              type="text"
              autoComplete="off"
              autoCorrect="off"
              autoCapitalize="off"
              spellCheck={false}
              data-lpignore="true"
              placeholder="Table (/)..."
              value={filters.table_name ?? ''}
              onChange={(e) => handleFilterChange({ table_name: e.target.value || undefined, page: 1 })}
              className="pl-8 pr-2.5 py-1.5 bg-linear-canvas border border-linear-hairline rounded-lg text-xs text-linear-ink placeholder-linear-ink-subtle focus:outline-none focus:border-linear-primary w-32 sm:w-36 font-mono"
            />
          </div>

          {/* Sequence ID */}
          <div className="relative">
            <Hash className="w-3.5 h-3.5 text-linear-ink-subtle absolute left-2.5 top-1/2 -translate-y-1/2 pointer-events-none" />
            <input
              id="audit-log-seq-filter"
              name="sequence_id"
              type="number"
              autoComplete="off"
              data-lpignore="true"
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
              id="audit-log-blind-id-filter"
              name="blind_id"
              type="text"
              autoComplete="off"
              autoCorrect="off"
              autoCapitalize="off"
              spellCheck={false}
              data-lpignore="true"
              placeholder="Blind ID..."
              title="HMAC-SHA256 blind index query for encrypted National ID"
              value={filters.national_id_search ?? ''}
              onChange={(e) => handleFilterChange({ national_id_search: e.target.value || undefined, page: 1 })}
              className="pl-8 pr-2.5 py-1.5 bg-linear-canvas border border-linear-hairline rounded-lg text-xs text-linear-ink placeholder-linear-ink-subtle focus:outline-none focus:border-linear-primary w-32 sm:w-40 font-mono"
            />
          </div>

          {/* Action filter */}
          <div className="flex items-center space-x-1">
            <Filter className="w-3 h-3 text-linear-ink-muted" />
            <select
              value={filters.action ?? ''}
              onChange={(e) => {
                const value = e.target.value;
                const action = ['INSERT', 'UPDATE', 'DELETE'].includes(value)
                  ? value as NonNullable<AuditLogFilters['action']>
                  : undefined;
                handleFilterChange({ action, page: 1 });
              }}
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
            onChange={(e) => {
              const value = e.target.value;
              const severity = ['INFO', 'WARNING', 'CRITICAL'].includes(value)
                ? value as NonNullable<AuditLogFilters['severity']>
                : undefined;
              handleFilterChange({ severity, page: 1 });
            }}
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
              <td colSpan={8}>
                <EmptyState
                  icon={<Hash className="w-6 h-6" />}
                  title="No audit entries matching filters"
                  description="Try clearing active filter chips or adjusting query parameters."
                  portalTheme="auditor"
                />
              </td>
            </tr>
          </tbody>
        ) : (
          <DataTable.Body portalTheme="auditor">
            {items.map((entry, idx) => (
              <AuditRow
                key={entry.sequence_id}
                ref={(el) => {
                  rowRefs.current[idx] = el;
                }}
                entry={entry}
                isTampered={incident.tamperedSeqId === entry.sequence_id}
                tamperDetails={incident.tamperedSeqId === entry.sequence_id ? incident.details : undefined}
                isTargetSeq={targetSeqId === entry.sequence_id}
                isSelected={openRowSeq === entry.sequence_id}
                isFocused={focusedRowIndex === idx}
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
            onClick={goToNextPage}
            disabled={(filters.page ?? 1) >= totalPages || isFetching || (data?.has_more === false)}
            rightIcon={<ChevronRight className="w-3 h-3" />}
          >
            Next
          </Button>
        </div>
      )}
    </div>
  );
}
