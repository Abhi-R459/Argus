import { useState, useEffect, useRef, useMemo } from 'react';
import { useSearchParams, useNavigate } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { useAuth } from '@clerk/clerk-react';
import {
  GitBranch, Search, Filter, ShieldAlert, ShieldCheck,
  ArrowRight, ArrowLeft, Copy, Check, Clock,
  ExternalLink, Hash, Database, Layers, Shield
} from 'lucide-react';
import {
  fetchAuditChain,
  useIncidentStatus,
  type ChainEntry,
} from '../../services/auditService';
import DiffViewer from '../../components/auditor/DiffViewer';
import RefreshButton from '../../components/common/RefreshButton';
import { DataTable } from '../../components/common/DataTable';
import { FilterBar, type ActiveFilterItem } from '../../components/common/FilterBar';
import { DetailSheet } from '../../components/common/DetailSheet';
import { Button } from '../../components/common/Button';
import { LiveStreamBadge } from '../../components/common/LiveStreamBadge';
import { SkeletonRows } from '../../components/common/SkeletonRows';
import { EmptyState } from '../../components/common/EmptyState';
import { CopyButton } from '../../components/common/CopyButton';
import { useKeyboardNav } from '../../hooks/useKeyboardNav';
import { formatRelativeTime, truncateHash } from '../../lib/format';
import { getActionSemantic, getSeverityDotClass } from '../../lib/semantics';

export default function AuditChainPage() {
  const { getToken } = useAuth();
  const [searchParams, setSearchParams] = useSearchParams();
  const navigate = useNavigate();
  const incident = useIncidentStatus();

  // Search input ref for keyboard '/' shortcut
  const searchInputRef = useRef<HTMLInputElement>(null);

  // URL query parameter sync (?seq=)
  const seqParam = searchParams.get('seq');
  const initialSeq = seqParam ? parseInt(seqParam, 10) : null;

  const [activeAroundSeq, setActiveAroundSeq] = useState<number | null>(
    !isNaN(Number(initialSeq)) && initialSeq !== null ? initialSeq : null
  );
  const [seqInput, setSeqInput] = useState<string>(activeAroundSeq ? String(activeAroundSeq) : '');

  // Keep activeAroundSeq synced when URL searchParams (?seq=) changes
  useEffect(() => {
    const s = searchParams.get('seq');
    const parsed = s ? parseInt(s, 10) : null;
    if (parsed !== null && !isNaN(parsed)) {
      setActiveAroundSeq(parsed);
      setSeqInput(String(parsed));
    } else if (s === null && activeAroundSeq !== null) {
      setActiveAroundSeq(null);
      setSeqInput('');
    }
  }, [searchParams]);
  const [selectedTable, setSelectedTable] = useState<string>('');
  const [selectedAction, setSelectedAction] = useState<string>('');
  const [pageOffset, setPageOffset] = useState<number>(0);
  const [selectedBlock, setSelectedBlock] = useState<ChainEntry | null>(null);
  const [focusedRowIndex, setFocusedRowIndex] = useState<number>(-1);
  const [copiedHash, setCopiedHash] = useState<string | null>(null);

  // Search dropdown & keyboard navigation state
  const [isSearchDropdownOpen, setIsSearchDropdownOpen] = useState<boolean>(false);
  const [highlightedSearchIdx, setHighlightedSearchIdx] = useState<number>(0);
  const searchDropdownRef = useRef<HTMLDivElement>(null);
  const rowRefs = useRef<(HTMLTableRowElement | null)[]>([]);

  // Real-time streaming state & inspection freeze
  const [isStreaming, setIsStreaming] = useState<boolean>(true);
  const [lastFetchedAt, setLastFetchedAt] = useState<Date>(new Date());
  const [frozenEntries, setFrozenEntries] = useState<ChainEntry[] | null>(null);
  const [pendingIncomingEntries, setPendingIncomingEntries] = useState<ChainEntry[] | null>(null);
  const [freshSeqIds, setFreshSeqIds] = useState<Set<number>>(new Set());
  const prevHighestSeqRef = useRef<number | null>(null);

  const PAGE_LIMIT = 20;

  // React Query fetching chain
  const {
    data: fetchedEntries = [],
    isLoading,
    refetch,
    isFetching,
    dataUpdatedAt,
  } = useQuery({
    queryKey: ['audit-chain-explorer', activeAroundSeq, pageOffset, selectedTable, selectedAction],
    queryFn: async () => {
      const data = await fetchAuditChain(getToken, {
        limit: PAGE_LIMIT,
        offset: activeAroundSeq ? undefined : pageOffset,
        around_seq: activeAroundSeq ?? undefined,
        table_name: selectedTable || undefined,
        action: selectedAction || undefined,
      });
      return data;
    },
    refetchInterval: isStreaming ? 2500 : false,
  });

  // Track fetch timestamp for LiveStreamBadge
  useEffect(() => {
    if (dataUpdatedAt) {
      setLastFetchedAt(new Date(dataUpdatedAt));
    }
  }, [dataUpdatedAt]);

  // Handle incoming stream reconciliation & inspection freeze
  useEffect(() => {
    if (fetchedEntries.length === 0) return;

    const currentHighest = Math.max(...fetchedEntries.map((e) => e.entry_id));

    // Detect fresh entries for 300ms micro-flash
    if (prevHighestSeqRef.current !== null && currentHighest > prevHighestSeqRef.current) {
      const newlyArrived = fetchedEntries
        .filter((e) => e.entry_id > (prevHighestSeqRef.current ?? 0))
        .map((e) => e.entry_id);

      if (newlyArrived.length > 0) {
        setFreshSeqIds(new Set(newlyArrived));
        const timer = setTimeout(() => setFreshSeqIds(new Set()), 600);
        return () => clearTimeout(timer);
      }
    }

    prevHighestSeqRef.current = currentHighest;

    // Case 1: User is actively inspecting a block -> Freeze visible rows to avoid jarring CLS
    if (selectedBlock !== null) {
      if (frozenEntries === null) {
        setFrozenEntries(fetchedEntries);
      } else {
        // Compare with frozen head to compute pending queue
        const frozenHighest = Math.max(...frozenEntries.map((e) => e.entry_id));
        if (currentHighest > frozenHighest) {
          setPendingIncomingEntries(fetchedEntries);
        }
      }
    } else {
      // Case 2: User is idle -> Flow live data smoothly
      setFrozenEntries(null);
      setPendingIncomingEntries(null);
    }
  }, [fetchedEntries, selectedBlock, frozenEntries]);

  // The active rendered list (frozen if inspecting, otherwise live)
  const displayEntries = frozenEntries ?? fetchedEntries;

  // Unfreeze and catch up to latest stream
  const handleCatchUp = () => {
    if (pendingIncomingEntries) {
      setFrozenEntries(pendingIncomingEntries);
      setPendingIncomingEntries(null);
    } else {
      setFrozenEntries(null);
    }
  };

  // Sync selectedBlock only if inspect=true is requested (e.g. clicking the orange button)
  useEffect(() => {
    if (activeAroundSeq && displayEntries.length > 0) {
      const matchIndex = displayEntries.findIndex((e) => e.entry_id === activeAroundSeq);
      if (matchIndex !== -1) {
        setFocusedRowIndex(matchIndex);
        setTimeout(() => {
          rowRefs.current[matchIndex]?.scrollIntoView({ behavior: 'smooth', block: 'center' });
        }, 50);

        const shouldInspect = searchParams.get('inspect') === 'true';
        if (shouldInspect) {
          setSelectedBlock(displayEntries[matchIndex]);
        }
      }
    }
  }, [activeAroundSeq, displayEntries, searchParams]);

  // Keyboard navigation hook
  useKeyboardNav({
    itemCount: displayEntries.length,
    selectedIndex: focusedRowIndex,
    onSelectIndex: (idx) => {
      setFocusedRowIndex(idx);
      if (selectedBlock) {
        // If drawer is open, advance inspection to focused block
        setSelectedBlock(displayEntries[idx]);
      }
    },
    onPeek: (idx) => {
      const target = displayEntries[idx];
      if (target) {
        setSelectedBlock((curr) => (curr?.entry_id === target.entry_id ? null : target));
      }
    },
    onDismiss: () => {
      setSelectedBlock(null);
      setFrozenEntries(null);
      setPendingIncomingEntries(null);
    },
    onTogglePause: () => setIsStreaming((prev) => !prev),
    searchInputRef,
    enabled: true,
  });

  // Click outside to dismiss search dropdown
  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (
        searchDropdownRef.current &&
        !searchDropdownRef.current.contains(event.target as Node) &&
        searchInputRef.current &&
        !searchInputRef.current.contains(event.target as Node)
      ) {
        setIsSearchDropdownOpen(false);
      }
    }
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  // Auto-scroll focused row into view when focusedRowIndex changes
  useEffect(() => {
    const rowEl = rowRefs.current[focusedRowIndex];
    if (rowEl) {
      rowEl.scrollIntoView({ block: 'nearest', behavior: 'smooth' });
    }
  }, [focusedRowIndex]);

  // Keep rowRefs aligned with displayEntries
  useEffect(() => {
    rowRefs.current = rowRefs.current.slice(0, displayEntries.length);
    if (displayEntries.length > 0 && focusedRowIndex >= displayEntries.length) {
      setFocusedRowIndex(0);
    }
  }, [displayEntries.length, focusedRowIndex]);

  // Compute live search matching results
  type SearchOption =
    | { type: 'direct'; seq: number; label: string }
    | { type: 'entry'; entry: ChainEntry };

  const searchOptions: SearchOption[] = useMemo(() => {
    const q = seqInput.trim();
    if (!q) return [];

    const options: SearchOption[] = [];
    const qLower = q.toLowerCase();
    const cleanNumStr = q.replace(/^#/, '').trim();
    const isNum = /^\d+$/.test(cleanNumStr);
    const qNum = isNum ? parseInt(cleanNumStr, 10) : null;

    // Filter matching blocks from displayEntries
    const matchedEntries = displayEntries.filter((e) => {
      const matchSeq = cleanNumStr ? String(e.entry_id).includes(cleanNumStr) : false;
      const matchOp = e.operation.toLowerCase().includes(qLower);
      const matchTable = e.table_name.toLowerCase().includes(qLower);
      const matchActor = e.actor_email.toLowerCase().includes(qLower);
      const matchHash = e.hash.toLowerCase().includes(qLower);
      return matchSeq || matchOp || matchTable || matchActor || matchHash;
    });

    // If positive integer, provide direct jump action
    if (qNum !== null && qNum > 0) {
      options.push({
        type: 'direct',
        seq: qNum,
        label: `Jump to Block #${qNum}`,
      });
    }

    // Add matching entries up to 8
    matchedEntries.slice(0, 8).forEach((entry) => {
      options.push({
        type: 'entry',
        entry,
      });
    });

    return options;
  }, [seqInput, displayEntries]);

  const handleSelectOption = (option: SearchOption) => {
    setIsSearchDropdownOpen(false);
    if (option.type === 'direct') {
      setActiveAroundSeq(option.seq);
      setSearchParams({ seq: String(option.seq) });
      setPageOffset(0);
      setFrozenEntries(null);
      setSeqInput(String(option.seq));
    } else {
      const entry = option.entry;
      setActiveAroundSeq(entry.entry_id);
      setSearchParams({ seq: String(entry.entry_id) });
      setPageOffset(0);
      setFrozenEntries(null);
      setSelectedBlock(entry);
      setSeqInput(String(entry.entry_id));
      const idx = displayEntries.findIndex((e) => e.entry_id === entry.entry_id);
      if (idx !== -1) {
        setFocusedRowIndex(idx);
      }
    }
  };

  const handleSearchInputKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (!isSearchDropdownOpen || searchOptions.length === 0) {
      if (e.key === 'Escape') {
        setIsSearchDropdownOpen(false);
        searchInputRef.current?.blur();
      }
      return;
    }

    if (e.key === 'ArrowDown') {
      e.preventDefault();
      setHighlightedSearchIdx((prev) => (prev + 1) % searchOptions.length);
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      setHighlightedSearchIdx((prev) => (prev - 1 + searchOptions.length) % searchOptions.length);
    } else if (e.key === 'Enter') {
      e.preventDefault();
      if (searchOptions[highlightedSearchIdx]) {
        handleSelectOption(searchOptions[highlightedSearchIdx]);
      } else {
        handleJumpSubmit(e);
      }
    } else if (e.key === 'Escape') {
      e.preventDefault();
      setIsSearchDropdownOpen(false);
    }
  };

  // Jump to specific sequence
  const handleJumpSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setIsSearchDropdownOpen(false);
    const val = parseInt(seqInput.trim(), 10);
    if (!isNaN(val) && val > 0) {
      setActiveAroundSeq(val);
      setSearchParams({ seq: String(val) });
      setPageOffset(0);
      setFrozenEntries(null);
    } else {
      handleJumpToHead();
    }
  };

  // Jump to head
  const handleJumpToHead = () => {
    setIsSearchDropdownOpen(false);
    setActiveAroundSeq(null);
    setSeqInput('');
    setSearchParams({});
    setPageOffset(0);
    setFrozenEntries(null);
  };

  // Jump to compromise
  const handleJumpToCompromise = () => {
    if (incident.tamperedSeqId) {
      setActiveAroundSeq(incident.tamperedSeqId);
      setSeqInput(String(incident.tamperedSeqId));
      setSearchParams({ seq: String(incident.tamperedSeqId) });
      setPageOffset(0);
      setFrozenEntries(null);
    }
  };

  // Copy hash helper
  const handleCopy = (text: string, label: string) => {
    navigator.clipboard.writeText(text);
    setCopiedHash(label);
    setTimeout(() => setCopiedHash(null), 2000);
  };

  // Active filter items for FilterBar
  const activeFilters: ActiveFilterItem[] = [];
  if (selectedTable) {
    activeFilters.push({
      id: 'table',
      label: 'Table',
      value: selectedTable,
      onRemove: () => setSelectedTable(''),
    });
  }
  if (selectedAction) {
    activeFilters.push({
      id: 'action',
      label: 'Action',
      value: selectedAction,
      onRemove: () => setSelectedAction(''),
    });
  }
  if (activeAroundSeq !== null) {
    activeFilters.push({
      id: 'around_seq',
      label: 'Around Block',
      value: `#${activeAroundSeq}`,
      onRemove: handleJumpToHead,
    });
  }

  const handleClearAllFilters = () => {
    setSelectedTable('');
    setSelectedAction('');
    handleJumpToHead();
  };

  const minSeq = displayEntries.length > 0 ? Math.min(...displayEntries.map((e) => e.entry_id)) : 0;
  const maxSeq = displayEntries.length > 0 ? Math.max(...displayEntries.map((e) => e.entry_id)) : 0;
  const pendingCount = pendingIncomingEntries
    ? Math.max(0, Math.max(...pendingIncomingEntries.map((e) => e.entry_id)) - (frozenEntries ? Math.max(...frozenEntries.map((e) => e.entry_id)) : 0))
    : 0;

  return (
    <div className="space-y-4 pb-10">
      {/* Top Header & Operational Status Bar */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pt-1">
        <div className="flex items-center space-x-3">
          <div className="w-8 h-8 rounded-lg bg-linear-surface-2 border border-linear-hairline flex items-center justify-center text-linear-primary shadow-xs">
            <GitBranch className="w-4 h-4" />
          </div>
          <div>
            <h2 className="text-lg font-bold text-linear-ink flex items-center space-x-2 leading-tight">
              <span>Cryptographic Chain Explorer</span>
              <span className="text-[11px] px-2 py-0.5 rounded font-mono bg-linear-surface-2 text-linear-primary border border-linear-hairline">
                SHA-256
              </span>
            </h2>
            <p className="text-xs text-linear-ink-muted">
              Keyset-paginated ledger continuity and immutable block inspection.
            </p>
          </div>
        </div>

        {/* Live Controls */}
        <div className="flex items-center space-x-2.5">
          {incident.isCompromised && incident.tamperedSeqId && (
            <Button
              variant="danger"
              size="sm"
              portalTheme="auditor"
              onClick={handleJumpToCompromise}
              leftIcon={<ShieldAlert className="w-3.5 h-3.5" />}
              className="text-status-warning bg-status-warning/15 border-status-warning/40 hover:bg-status-warning/25"
            >
              Breach at #{incident.tamperedSeqId}
            </Button>
          )}

          <LiveStreamBadge
            isStreaming={isStreaming}
            onToggleStream={() => setIsStreaming((prev) => !prev)}
            lastFetchedAt={lastFetchedAt}
            portalTheme="auditor"
          />

          <RefreshButton
            onRefresh={() => refetch()}
            label="Sync"
            variant="dark"
            title="Sync chain now"
            className="px-2.5 py-1 rounded-lg text-xs"
          />
        </div>
      </div>

      {/* Metric Telemetry Cards */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        <div className="bg-linear-surface-1 border border-linear-hairline rounded-lg p-3">
          <div className="flex items-center justify-between">
            <span className="text-[11px] text-linear-ink-muted font-medium">Blocks In Scope</span>
            <Layers className="w-3.5 h-3.5 text-linear-primary" />
          </div>
          <p className="text-base font-bold font-mono text-linear-ink mt-1">
            {displayEntries.length}
          </p>
          <span className="text-[10px] text-linear-ink-muted font-mono block">
            {displayEntries.length > 0 ? `Seq #${minSeq} → #${maxSeq}` : 'Empty'}
          </span>
        </div>

        <div className="bg-linear-surface-1 border border-linear-hairline rounded-lg p-3">
          <div className="flex items-center justify-between">
            <span className="text-[11px] text-linear-ink-muted font-medium">Chain Integrity</span>
            <Shield className="w-3.5 h-3.5 text-linear-success" />
          </div>
          <div className="mt-1 flex items-center space-x-2">
            <span
              className={`w-2 h-2 rounded-full ${
                incident.isCompromised ? 'bg-status-warning' : 'bg-linear-success'
              }`}
            />
            <span
              className={`text-xs font-bold font-mono ${
                incident.isCompromised ? 'text-status-warning' : 'text-linear-success'
              }`}
            >
              {incident.isCompromised ? 'TAMPERED' : 'SEALED & INTACT'}
            </span>
          </div>
          <span className="text-[10px] text-linear-ink-muted font-mono block">
            {incident.isCompromised ? `Breach: #${incident.tamperedSeqId}` : '0 hash anomalies'}
          </span>
        </div>

        <div className="bg-linear-surface-1 border border-linear-hairline rounded-lg p-3">
          <div className="flex items-center justify-between">
            <span className="text-[11px] text-linear-ink-muted font-medium">External Anchor</span>
            <ShieldCheck className="w-3.5 h-3.5 text-sky-400" />
          </div>
          <div className="mt-1 flex items-center space-x-2">
            <span
              className={`w-2 h-2 rounded-full ${
                incident.anchorMismatch ? 'bg-status-warning' : 'bg-sky-400'
              }`}
            />
            <span
              className={`text-xs font-bold font-mono ${
                incident.anchorMismatch ? 'text-status-warning' : 'text-sky-400'
              }`}
            >
              {incident.anchorMismatch ? 'MISMATCH' : 'SYNCHRONIZED'}
            </span>
          </div>
          <span className="text-[10px] text-linear-ink-muted font-mono block">
            Ed25519 Signed Commit
          </span>
        </div>

        <div className="bg-linear-surface-1 border border-linear-hairline rounded-lg p-3">
          <div className="flex items-center justify-between">
            <span className="text-[11px] text-linear-ink-muted font-medium">Navigation Window</span>
            <Hash className="w-3.5 h-3.5 text-amber-400" />
          </div>
          <p className="text-xs font-bold font-mono text-linear-ink mt-1 truncate">
            {activeAroundSeq ? `Centered on #${activeAroundSeq}` : `Latest (Offset ${pageOffset})`}
          </p>
          <span className="text-[10px] text-linear-ink-muted font-mono block">
            {activeAroundSeq ? 'Fixed Window' : 'Keyset Walk'}
          </span>
        </div>
      </div>

      {/* Filter & Jump Toolbar */}
      <FilterBar activeFilters={activeFilters} onClearAll={handleClearAllFilters} portalTheme="auditor" className="relative z-30">
        {/* Sequence jump search */}
        <form onSubmit={handleJumpSubmit} autoComplete="off" className="flex items-center gap-2 flex-1 max-w-md relative">
          <div className="relative flex-1">
            <Search className="w-3.5 h-3.5 text-linear-ink-subtle absolute left-2.5 top-1/2 -translate-y-1/2 pointer-events-none" />
            <input
              ref={searchInputRef}
              id="audit-chain-seq-search"
              name="search"
              type="text"
              autoComplete="off"
              autoCorrect="off"
              autoCapitalize="off"
              spellCheck={false}
              data-lpignore="true"
              data-form-type="other"
              value={seqInput}
              onChange={(e) => {
                setSeqInput(e.target.value);
                setIsSearchDropdownOpen(e.target.value.trim().length > 0);
                setHighlightedSearchIdx(0);
              }}
              onFocus={() => {
                if (seqInput.trim().length > 0) {
                  setIsSearchDropdownOpen(true);
                }
              }}
              onKeyDown={handleSearchInputKeyDown}
              placeholder="Search block sequence # (Press / to focus)..."
              className="w-full bg-linear-canvas border border-linear-hairline rounded-lg pl-8 pr-3 py-1.5 text-xs text-linear-ink placeholder-linear-ink-subtle focus:outline-none focus:border-linear-primary font-mono transition-colors duration-150"
            />

            {/* Live Search Matching Dropdown */}
            {isSearchDropdownOpen && seqInput.trim().length > 0 && (
              <div
                ref={searchDropdownRef}
                className="absolute left-0 right-0 top-full mt-1.5 z-50 bg-linear-surface-1 border border-linear-hairline-strong rounded-xl shadow-2xl backdrop-blur-xl ring-1 ring-black/60 overflow-hidden animate-in fade-in slide-in-from-top-1 duration-150 origin-top"
              >
                <div className="px-3 py-1.5 text-[10px] uppercase font-mono font-semibold text-linear-ink-muted border-b border-linear-hairline bg-linear-surface-2/70 flex items-center justify-between">
                  <span>
                    {searchOptions.length > 0
                      ? `Matching Blocks (${searchOptions.length})`
                      : 'No Matching Blocks'}
                  </span>
                  <span className="text-linear-ink-subtle lowercase">
                    ↑↓ navigate • ↵ select • esc close
                  </span>
                </div>

                <div className="max-h-64 overflow-y-auto divide-y divide-linear-hairline/40">
                  {searchOptions.length === 0 ? (
                    <div className="px-3 py-4 text-center text-xs text-linear-ink-muted font-mono">
                      No blocks matching "{seqInput.trim()}" in active buffer.
                    </div>
                  ) : (
                    searchOptions.map((opt, idx) => {
                      const isHighlighted = idx === highlightedSearchIdx;
                      if (opt.type === 'direct') {
                        return (
                          <div
                            key={`direct-${opt.seq}`}
                            onMouseEnter={() => setHighlightedSearchIdx(idx)}
                            onClick={() => handleSelectOption(opt)}
                            className={`px-3 py-2 cursor-pointer flex items-center justify-between text-xs transition-colors duration-100 ${
                              isHighlighted
                                ? 'bg-linear-primary/20 text-linear-ink border-l-2 border-linear-primary'
                                : 'hover:bg-linear-surface-2/60 text-linear-ink border-l-2 border-transparent'
                            }`}
                          >
                            <div className="flex items-center space-x-2">
                              <Hash className="w-3.5 h-3.5 text-linear-primary flex-shrink-0" />
                              <span className="font-semibold">{opt.label}</span>
                            </div>
                            <span className="text-[10px] font-mono text-linear-primary bg-linear-primary/10 border border-linear-primary/30 px-1.5 py-0.5 rounded">
                              Direct Jump ↵
                            </span>
                          </div>
                        );
                      }

                      const entry = opt.entry;
                      const opSemantic = getActionSemantic(entry.operation, entry.table_name, 'auditor');
                      return (
                        <div
                          key={`entry-${entry.entry_id}`}
                          onMouseEnter={() => setHighlightedSearchIdx(idx)}
                          onClick={() => handleSelectOption(opt)}
                          className={`px-3 py-2 cursor-pointer flex items-center justify-between text-xs transition-colors duration-100 ${
                            isHighlighted
                              ? 'bg-linear-primary/20 text-linear-ink border-l-2 border-linear-primary'
                              : 'hover:bg-linear-surface-2/60 text-linear-ink border-l-2 border-transparent'
                          }`}
                        >
                          <div className="flex items-center space-x-2 min-w-0">
                            <span
                              className={`w-1.5 h-1.5 rounded-full flex-shrink-0 ${getSeverityDotClass(
                                entry.severity
                              )}`}
                            />
                            <span className="font-mono font-bold text-linear-ink">
                              #{entry.entry_id}
                            </span>
                            <span
                              className={`text-[10px] font-mono font-bold px-1.5 py-0.5 rounded border ${opSemantic.className}`}
                            >
                              {entry.operation}
                            </span>
                            <span className="text-linear-ink-muted font-mono truncate text-[11px]">
                              {entry.table_name}
                            </span>
                          </div>
                          <div className="flex items-center space-x-2 text-[11px] text-linear-ink-muted ml-2 shrink-0">
                            <span className="truncate max-w-[110px] hidden sm:inline">
                              {entry.actor_email}
                            </span>
                            <span className="font-mono text-[10px] text-linear-ink-subtle">
                              {formatRelativeTime(entry.timestamp)}
                            </span>
                          </div>
                        </div>
                      );
                    })
                  )}
                </div>
              </div>
            )}
          </div>
          <Button
            type="submit"
            variant="secondary"
            size="sm"
            portalTheme="auditor"
            className="h-8 px-3"
          >
            Jump
          </Button>
          {activeAroundSeq !== null && (
            <Button
              type="button"
              variant="ghost"
              size="sm"
              portalTheme="auditor"
              onClick={handleJumpToHead}
              className="h-8 px-2.5 font-mono text-linear-ink-muted"
              title="Return to latest head"
              aria-label="Return to latest head"
            >
              Head
            </Button>
          )}
        </form>

        {/* Dropdowns */}
        <div className="flex items-center gap-2">
          <div className="flex items-center space-x-1">
            <Filter className="w-3 h-3 text-linear-ink-muted" />
            <select
              value={selectedTable}
              onChange={(e) => {
                setSelectedTable(e.target.value);
                setPageOffset(0);
              }}
              className="bg-linear-canvas border border-linear-hairline rounded-lg px-2.5 py-1.5 text-xs text-linear-ink focus:outline-none focus:border-linear-primary font-mono"
            >
              <option value="">All Tables</option>
              <option value="employees">employees</option>
              <option value="salary_history">salary_history</option>
            </select>
          </div>

          <select
            value={selectedAction}
            onChange={(e) => {
              setSelectedAction(e.target.value);
              setPageOffset(0);
            }}
            className="bg-linear-canvas border border-linear-hairline rounded-lg px-2.5 py-1.5 text-xs text-linear-ink focus:outline-none focus:border-linear-primary font-mono"
          >
            <option value="">All Operations</option>
            <option value="INSERT">INSERT</option>
            <option value="UPDATE">UPDATE</option>
            <option value="DELETE">DELETE</option>
          </select>
        </div>
      </FilterBar>

      {/* Inspection Freeze Banner (Datadog-style catch up) */}
      {pendingCount > 0 && (
        <div className="flex items-center justify-between px-3.5 py-2 rounded-lg bg-linear-primary/15 border border-linear-primary/30 text-linear-ink text-xs animate-in fade-in duration-200">
          <span className="flex items-center gap-2">
            <span className="w-2 h-2 rounded-full bg-linear-primary animate-pulse" />
            <span className="font-mono">
              Stream paused during inspection: <strong>{pendingCount}</strong> new blocks received.
            </span>
          </span>
          <Button
            type="button"
            variant="primary"
            size="xs"
            portalTheme="auditor"
            onClick={handleCatchUp}
          >
            Catch Up ↑
          </Button>
        </div>
      )}

      {/* Full-Width Operational Table Canvas */}
      <div className="w-full space-y-3 min-h-[520px]">
        <DataTable.Root portalTheme="auditor">
            <DataTable.Header portalTheme="auditor">
              <tr>
                <DataTable.HeadCell className="w-16">Seq #</DataTable.HeadCell>
                <DataTable.HeadCell className="w-20">Action</DataTable.HeadCell>
                <DataTable.HeadCell className="w-28">Table</DataTable.HeadCell>
                <DataTable.HeadCell>Actor</DataTable.HeadCell>
                <DataTable.HeadCell>Computed Hash</DataTable.HeadCell>
                <DataTable.HeadCell>Previous Hash</DataTable.HeadCell>
                <DataTable.HeadCell align="right">Recorded</DataTable.HeadCell>
              </tr>
            </DataTable.Header>

            {isLoading ? (
              <SkeletonRows rowCount={10} columnCount={7} portalTheme="auditor" />
            ) : displayEntries.length === 0 ? (
              <tbody>
                <tr>
                  <td colSpan={7}>
                    <EmptyState
                      icon={<GitBranch className="w-6 h-6" />}
                      title="No chain entries found"
                      description="Try resetting active filters or jump to head."
                      portalTheme="auditor"
                    />
                  </td>
                </tr>
              </tbody>
            ) : (
              <DataTable.Body portalTheme="auditor">
                {displayEntries.map((entry, idx) => {
                  const isTampered = incident.tamperedSeqId === entry.entry_id;
                  const isSelected = selectedBlock?.entry_id === entry.entry_id;
                  const isFresh = freshSeqIds.has(entry.entry_id);
                  const actionSemantic = getActionSemantic(entry.operation, entry.table_name, 'auditor');

                  return (
                    <DataTable.Row
                      key={entry.entry_id}
                      ref={(el) => {
                        rowRefs.current[idx] = el;
                      }}
                      isSelected={isSelected}
                      isFocused={focusedRowIndex === idx}
                      isTampered={isTampered}
                      isFresh={isFresh}
                      portalTheme="auditor"
                      onClick={() => {
                        setFocusedRowIndex(idx);
                        setSelectedBlock(entry);
                      }}
                      className={isFresh ? 'animate-row-flash' : ''}
                    >
                      {/* Seq # */}
                      <DataTable.Cell tabularNums mono className="font-bold">
                        <div className="flex items-center space-x-1.5">
                          <span className={`w-1.5 h-1.5 rounded-full ${isTampered ? 'bg-status-warning' : getSeverityDotClass(entry.severity)}`} />
                          <span className={isTampered ? 'text-status-warning' : 'text-linear-ink'}>
                            #{entry.entry_id}
                          </span>
                        </div>
                      </DataTable.Cell>

                      {/* Action */}
                      <DataTable.Cell>
                        <span
                          className={`text-[10px] font-mono font-bold px-1.5 py-0.5 rounded border ${
                            actionSemantic.className
                          }`}
                        >
                          {entry.operation}
                        </span>
                      </DataTable.Cell>

                      {/* Table */}
                      <DataTable.Cell mono className="text-linear-ink-muted">
                        {entry.table_name}
                      </DataTable.Cell>

                      {/* Actor */}
                      <DataTable.Cell className="text-linear-ink-muted max-w-[140px] truncate">
                        {entry.actor_email}
                      </DataTable.Cell>

                      {/* Computed Hash */}
                      <DataTable.Cell mono>
                        <CopyButton
                          text={entry.hash}
                          label={truncateHash(entry.hash)}
                          portalTheme="auditor"
                          title="Click to copy full hash"
                        />
                      </DataTable.Cell>

                      {/* Previous Hash */}
                      <DataTable.Cell mono className="text-linear-ink-subtle">
                        <span className="text-[11px]">
                          {truncateHash(entry.prev_hash || '0'.repeat(64))}
                        </span>
                      </DataTable.Cell>

                      {/* Recorded Time */}
                      <DataTable.Cell align="right" mono className="text-linear-ink-muted text-[11px]">
                        <span title={new Date(entry.timestamp).toLocaleString()}>
                          {formatRelativeTime(entry.timestamp)}
                        </span>
                      </DataTable.Cell>
                    </DataTable.Row>
                  );
                })}
              </DataTable.Body>
            )}
          </DataTable.Root>

          {/* Keyset Pagination Bar */}
          {!activeAroundSeq && displayEntries.length > 0 && (
            <div className="flex items-center justify-between px-1 py-1 text-xs">
              <Button
                type="button"
                variant="secondary"
                size="sm"
                portalTheme="auditor"
                onClick={() => setPageOffset((prev) => Math.max(0, prev - PAGE_LIMIT))}
                disabled={pageOffset === 0 || isFetching}
                leftIcon={<ArrowLeft className="w-3 h-3" />}
              >
                Newer Blocks
              </Button>

              <div className="text-linear-ink-muted font-mono text-[11px]">
                Offset: {pageOffset} — {pageOffset + displayEntries.length}
                <span className="ml-2 text-linear-ink-subtle">(Use J/K to navigate, Space to peek)</span>
              </div>

              <Button
                type="button"
                variant="secondary"
                size="sm"
                portalTheme="auditor"
                onClick={() => setPageOffset((prev) => prev + PAGE_LIMIT)}
                disabled={displayEntries.length < PAGE_LIMIT || isFetching}
                rightIcon={<ArrowRight className="w-3 h-3" />}
              >
                Older Blocks
              </Button>
            </div>
          )}
        </div>

        {/* Modal Inspector Dialog (Matching HR Add Personnel dialog UX) */}
        <DetailSheet
          isOpen={Boolean(selectedBlock)}
          onClose={() => {
            setSelectedBlock(null);
            setFrozenEntries(null);
            setPendingIncomingEntries(null);
          }}
          title={
            selectedBlock ? (
              <span className="flex items-center space-x-2">
                <span>Block #{selectedBlock.entry_id}</span>
                <span className="text-[10px] font-mono font-normal text-linear-primary bg-linear-primary/10 border border-linear-primary/30 px-1.5 py-0.5 rounded">
                  SHA-256
                </span>
              </span>
            ) : null
          }
          subtitle={
            selectedBlock ? (
              <span className="flex items-center space-x-2 font-mono text-[11px]">
                <span className="text-linear-ink font-semibold">{selectedBlock.table_name}</span>
                <span>•</span>
                <span>{new Date(selectedBlock.timestamp).toLocaleString()}</span>
              </span>
            ) : null
          }
          headerBadge={
            selectedBlock ? (
              <span
                className={`text-[10px] font-mono font-bold px-2 py-0.5 rounded border ${
                  getActionSemantic(selectedBlock.operation, selectedBlock.table_name, 'auditor').className
                }`}
              >
                {selectedBlock.operation}
              </span>
            ) : null
          }
          portalTheme="auditor"
          mode="modal"
          widthClass="max-w-2xl lg:max-w-3xl"
          footer={
            selectedBlock ? (
              <div className="flex items-center justify-between gap-3 w-full">
                <Button
                  type="button"
                  variant="ghost"
                  size="sm"
                  portalTheme="auditor"
                  onClick={() => {
                    setSelectedBlock(null);
                    setFrozenEntries(null);
                    setPendingIncomingEntries(null);
                  }}
                  className="text-linear-ink-muted hover:text-linear-ink"
                >
                  Close (Esc)
                </Button>

                <div className="flex items-center gap-2">
                  {(() => {
                    const empId =
                      (selectedBlock.new_value as any)?.employee_id ||
                      (selectedBlock.old_value as any)?.employee_id ||
                      (selectedBlock.new_value as any)?.id;

                    return (
                      <Button
                        type="button"
                        variant="secondary"
                        size="sm"
                        portalTheme="auditor"
                        onClick={() => {
                          const params = new URLSearchParams();
                          if (empId) params.set('emp_id', String(empId));
                          params.set('as_of', selectedBlock.timestamp);
                          navigate(`/auditor/time-travel?${params.toString()}`);
                        }}
                        leftIcon={<Clock className="w-3.5 h-3.5 text-linear-primary" />}
                      >
                        Time-Travel ⏱
                      </Button>
                    );
                  })()}

                  <Button
                    type="button"
                    variant="primary"
                    size="sm"
                    portalTheme="auditor"
                    onClick={() => navigate(`/auditor/log?seq=${selectedBlock.entry_id}`)}
                    leftIcon={<ExternalLink className="w-3.5 h-3.5" />}
                  >
                    View in Audit Log
                  </Button>
                </div>
              </div>
            ) : null
          }
        >
          {selectedBlock ? (
            <>
              {/* Cryptographic Linkage Details */}
              <div className="space-y-3">
                <h4 className="text-xs font-semibold text-linear-ink-muted uppercase tracking-wider flex items-center space-x-1.5">
                  <Hash className="w-3.5 h-3.5 text-linear-primary" />
                  <span>Cryptographic Proof</span>
                </h4>

                <div className="bg-linear-canvas rounded-lg p-3 border border-linear-hairline space-y-2.5 font-mono text-xs">
                  <div>
                    <div className="flex items-center justify-between text-linear-ink-muted text-[10px] mb-1">
                      <span>Entry Hash (H_i)</span>
                      <button
                        type="button"
                        onClick={() => handleCopy(selectedBlock.hash, 'drawer_entry_hash')}
                        aria-label="Copy entry hash"
                        className="text-linear-primary hover:text-linear-primary/80 flex items-center space-x-1 text-[10px] focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-linear-primary rounded px-1"
                      >
                        {copiedHash === 'drawer_entry_hash' ? (
                          <Check className="w-3 h-3 text-linear-success" />
                        ) : (
                          <Copy className="w-3 h-3" />
                        )}
                        <span>{copiedHash === 'drawer_entry_hash' ? 'Copied' : 'Copy'}</span>
                      </button>
                    </div>
                    <div className="text-linear-ink break-all bg-linear-surface-2 p-2 rounded border border-linear-hairline text-[11px]">
                      {selectedBlock.hash}
                    </div>
                  </div>

                  <div>
                    <div className="flex items-center justify-between text-linear-ink-muted text-[10px] mb-1">
                      <span>Previous Hash (H_{'{i-1}'})</span>
                      <button
                        type="button"
                        onClick={() => handleCopy(selectedBlock.prev_hash || '', 'drawer_prev_hash')}
                        aria-label="Copy previous hash"
                        className="text-linear-primary hover:text-linear-primary/80 flex items-center space-x-1 text-[10px] focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-linear-primary rounded px-1"
                      >
                        {copiedHash === 'drawer_prev_hash' ? (
                          <Check className="w-3 h-3 text-linear-success" />
                        ) : (
                          <Copy className="w-3 h-3" />
                        )}
                        <span>{copiedHash === 'drawer_prev_hash' ? 'Copied' : 'Copy'}</span>
                      </button>
                    </div>
                    <div className="text-linear-ink-muted break-all bg-linear-surface-2 p-2 rounded border border-linear-hairline text-[11px]">
                      {selectedBlock.prev_hash || '0'.repeat(64)}
                    </div>
                  </div>

                  <div className="pt-2 border-t border-linear-hairline text-[10px] text-linear-ink-muted">
                    <span>Formula: </span>
                    <code className="text-linear-primary">H_i = SHA-256(Canonical(R_i) || H_{'{i-1}'})</code>
                  </div>
                </div>
              </div>

              {/* Event Metadata */}
              <div className="grid grid-cols-2 gap-2 text-xs bg-linear-canvas p-3 rounded-lg border border-linear-hairline">
                <div>
                  <span className="text-[10px] text-linear-ink-muted uppercase tracking-wider block">Actor</span>
                  <span className="text-linear-ink font-medium truncate block">{selectedBlock.actor_email}</span>
                  <span className="text-[10px] text-linear-ink-subtle font-mono">({selectedBlock.actor_role})</span>
                </div>
                <div>
                  <span className="text-[10px] text-linear-ink-muted uppercase tracking-wider block">Recorded At</span>
                  <span className="text-linear-ink font-mono text-[11px] block">
                    {new Date(selectedBlock.timestamp).toLocaleString()}
                  </span>
                </div>
              </div>

              {/* Field Diff Viewer */}
              <div className="space-y-2">
                <h4 className="text-xs font-semibold text-linear-ink-muted uppercase tracking-wider flex items-center space-x-1.5">
                  <Database className="w-3.5 h-3.5 text-linear-primary" />
                  <span>Field-Level Payload Diff</span>
                </h4>
                <div className="bg-linear-canvas border border-linear-hairline rounded-lg p-3">
                  <DiffViewer
                    oldValue={selectedBlock.old_value}
                    newValue={selectedBlock.new_value}
                    operation={selectedBlock.operation}
                    isTampered={incident.tamperedSeqId === selectedBlock.entry_id}
                    tamperDetails={incident.tamperedSeqId === selectedBlock.entry_id ? incident.details : undefined}
                    sequenceId={selectedBlock.entry_id}
                  />
                </div>
              </div>
            </>
          ) : null}
        </DetailSheet>
      </div>
  );
}
