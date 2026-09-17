import { useState, useEffect } from 'react';
import { useSearchParams, useNavigate } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { useAuth } from '@clerk/clerk-react';
import {
  GitBranch, Search, Filter, RefreshCw, ShieldAlert, ShieldCheck,
  ArrowRight, ArrowLeft, X, Copy, Check, Clock,
  ExternalLink, Hash, Database, ChevronRight,
  Shield, Layers
} from 'lucide-react';
import {
  fetchAuditChain,
  useIncidentStatus,
  type ChainEntry,
  type AuditOperation,
  type Severity,
} from '../../services/auditService';
import DiffViewer from '../../components/auditor/DiffViewer';
import RefreshButton from '../../components/common/RefreshButton';

const OPERATION_STYLES: Record<AuditOperation, string> = {
  INSERT: 'bg-emerald-500/15 text-emerald-300 border-emerald-500/30',
  UPDATE: 'bg-amber-500/15 text-amber-300 border-amber-500/30',
  DELETE: 'bg-red-500/15 text-red-300 border-red-500/30',
};

const SEVERITY_DOT: Record<Severity, string> = {
  low: 'bg-slate-400',
  medium: 'bg-amber-400',
  high: 'bg-orange-400',
  critical: 'bg-red-500 shadow-[0_0_6px_rgba(239,68,68,0.7)]',
};

function truncateHash(hash: string, start = 8, end = 6): string {
  if (!hash) return '00000000…0000';
  if (hash.length <= start + end + 3) return hash;
  return `${hash.slice(0, start)}…${hash.slice(-end)}`;
}

export default function AuditChainPage() {
  const { getToken } = useAuth();
  const [searchParams, setSearchParams] = useSearchParams();
  const navigate = useNavigate();
  const incident = useIncidentStatus();

  // URL query parameter sync (?seq=)
  const seqParam = searchParams.get('seq');
  const initialSeq = seqParam ? parseInt(seqParam, 10) : null;

  const [activeAroundSeq, setActiveAroundSeq] = useState<number | null>(
    !isNaN(Number(initialSeq)) && initialSeq !== null ? initialSeq : null
  );
  const [seqInput, setSeqInput] = useState<string>(activeAroundSeq ? String(activeAroundSeq) : '');
  const [selectedTable, setSelectedTable] = useState<string>('');
  const [selectedAction, setSelectedAction] = useState<string>('');
  const [pageOffset, setPageOffset] = useState<number>(0);
  const [selectedBlock, setSelectedBlock] = useState<ChainEntry | null>(null);
  const [copiedHash, setCopiedHash] = useState<string | null>(null);

  const PAGE_LIMIT = 20;

  // React Query fetching chain
  const {
    data: chainEntries = [],
    isLoading,
    refetch,
    isFetching,
  } = useQuery({
    queryKey: ['audit-chain-explorer', activeAroundSeq, pageOffset, selectedTable, selectedAction],
    queryFn: () =>
      fetchAuditChain(getToken, {
        limit: PAGE_LIMIT,
        offset: activeAroundSeq ? undefined : pageOffset,
        around_seq: activeAroundSeq ?? undefined,
        table_name: selectedTable || undefined,
        action: selectedAction || undefined,
      }),
    refetchInterval: 2500,
  });

  // Keep selectedBlock in sync if query updates
  useEffect(() => {
    if (activeAroundSeq && chainEntries.length > 0) {
      const match = chainEntries.find((e) => e.entry_id === activeAroundSeq);
      if (match) {
        setSelectedBlock(match);
      }
    }
  }, [activeAroundSeq, chainEntries]);

  // Handle jump submit
  const handleJumpSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const val = parseInt(seqInput.trim(), 10);
    if (!isNaN(val) && val > 0) {
      setActiveAroundSeq(val);
      setSearchParams({ seq: String(val) });
      setPageOffset(0);
    } else {
      setActiveAroundSeq(null);
      setSearchParams({});
      setPageOffset(0);
    }
  };

  // Jump to head
  const handleJumpToHead = () => {
    setActiveAroundSeq(null);
    setSeqInput('');
    setSearchParams({});
    setPageOffset(0);
  };

  // Jump to compromise
  const handleJumpToCompromise = () => {
    if (incident.tamperedSeqId) {
      setActiveAroundSeq(incident.tamperedSeqId);
      setSeqInput(String(incident.tamperedSeqId));
      setSearchParams({ seq: String(incident.tamperedSeqId) });
      setPageOffset(0);
    }
  };

  // Copy hash helper
  const handleCopy = (text: string, label: string) => {
    navigator.clipboard.writeText(text);
    setCopiedHash(label);
    setTimeout(() => setCopiedHash(null), 2000);
  };

  const minSeq = chainEntries.length > 0 ? Math.min(...chainEntries.map((e) => e.entry_id)) : 0;
  const maxSeq = chainEntries.length > 0 ? Math.max(...chainEntries.map((e) => e.entry_id)) : 0;

  return (
    <div className="space-y-6 pb-12 animate-fade-cascade">
      {/* Page Title & Header Actions */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <div className="flex items-center space-x-2.5">
            <div className="w-9 h-9 rounded-xl bg-violet-600/20 border border-violet-500/40 flex items-center justify-center text-violet-400 shadow-xs">
              <GitBranch className="w-5 h-5" />
            </div>
            <div>
              <h2 className="text-xl font-bold text-slate-100 flex items-center space-x-2">
                <span>Cryptographic Chain Explorer</span>
                <span className="text-xs px-2 py-0.5 rounded-md font-mono bg-violet-500/15 text-violet-300 border border-violet-500/30">
                  SHA-256 Chain
                </span>
              </h2>
              <p className="text-xs text-slate-400 mt-0.5">
                Full-page ledger verification and block-level hash continuity inspection.
              </p>
            </div>
          </div>
        </div>

        {/* Quick actions */}
        <div className="flex items-center space-x-3">
          {incident.isCompromised && incident.tamperedSeqId && (
            <button
              onClick={handleJumpToCompromise}
              className="btn-press-sm px-3 py-1.5 rounded-lg bg-rose-500/20 hover:bg-rose-500/30 border border-rose-500/40 text-rose-300 text-xs font-semibold flex items-center space-x-1.5 transition-colors duration-150 shadow-xs animate-pulse"
            >
              <ShieldAlert className="w-3.5 h-3.5" />
              <span>Jump to Tampered Block #{incident.tamperedSeqId}</span>
            </button>
          )}
          <RefreshButton
            onRefresh={() => refetch()}
            label="Refresh"
            variant="dark"
            title="Refresh audit chain"
            className="px-3 py-1.5 rounded-lg text-xs"
          />
        </div>
      </div>

      {/* Metrics Banner */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="bg-[#0F172A]/80 border border-slate-800/80 rounded-xl p-4 shadow-xs">
          <div className="flex items-center justify-between">
            <span className="text-xs text-slate-400 font-medium">Blocks in Scope</span>
            <Layers className="w-4 h-4 text-violet-400" />
          </div>
          <p className="text-xl font-bold font-mono text-slate-100 mt-2">{chainEntries.length}</p>
          <span className="text-[11px] text-slate-400 font-mono mt-0.5 block">
            {chainEntries.length > 0 ? `Seq #${minSeq} → #${maxSeq}` : 'No entries'}
          </span>
        </div>

        <div className="bg-[#0F172A]/80 border border-slate-800/80 rounded-xl p-4 shadow-xs">
          <div className="flex items-center justify-between">
            <span className="text-xs text-slate-400 font-medium">Chain State</span>
            <Shield className="w-4 h-4 text-emerald-400" />
          </div>
          <div className="mt-2 flex items-center space-x-2">
            <span
              className={`w-2.5 h-2.5 rounded-full ${
                incident.isCompromised ? 'bg-rose-500 animate-ping' : 'bg-emerald-400 animate-pulse'
              }`}
            />
            <span
              className={`text-sm font-bold font-mono ${
                incident.isCompromised ? 'text-rose-400' : 'text-emerald-400'
              }`}
            >
              {incident.isCompromised ? 'TAMPERED' : 'INTACT'}
            </span>
          </div>
          <span className="text-[11px] text-slate-400 font-mono mt-0.5 block">
            {incident.isCompromised ? `Breach at #${incident.tamperedSeqId}` : '0 anomalies detected'}
          </span>
        </div>

        <div className="bg-[#0F172A]/80 border border-slate-800/80 rounded-xl p-4 shadow-xs">
          <div className="flex items-center justify-between">
            <span className="text-xs text-slate-400 font-medium">Anchor Synchronization</span>
            <ShieldCheck className="w-4 h-4 text-sky-400" />
          </div>
          <div className="mt-2 flex items-center space-x-2">
            <span
              className={`w-2.5 h-2.5 rounded-full ${
                incident.anchorMismatch ? 'bg-rose-500 animate-ping' : 'bg-sky-400'
              }`}
            />
            <span
              className={`text-sm font-bold font-mono ${
                incident.anchorMismatch ? 'text-rose-400' : 'text-sky-400'
              }`}
            >
              {incident.anchorMismatch ? 'MISMATCH' : 'SYNCHRONIZED'}
            </span>
          </div>
          <span className="text-[11px] text-slate-400 font-mono mt-0.5 block">
            Ed25519 external anchor cross-check
          </span>
        </div>

        <div className="bg-[#0F172A]/80 border border-slate-800/80 rounded-xl p-4 shadow-xs">
          <div className="flex items-center justify-between">
            <span className="text-xs text-slate-400 font-medium">Viewing Window</span>
            <Hash className="w-4 h-4 text-amber-400" />
          </div>
          <p className="text-sm font-bold font-mono text-slate-200 mt-2 truncate">
            {activeAroundSeq ? `Window around #${activeAroundSeq}` : `Latest Page (Offset ${pageOffset})`}
          </p>
          <span className="text-[11px] text-slate-400 font-mono mt-0.5 block">
            {activeAroundSeq ? 'Centered view' : 'Standard pagination'}
          </span>
        </div>
      </div>

      {/* Filter & Search Toolbar */}
      <div className="bg-[#0F172A]/80 border border-slate-800/80 rounded-2xl p-4 shadow-xs flex flex-col md:flex-row items-center justify-between gap-4">
        {/* Sequence jump form */}
        <form onSubmit={handleJumpSubmit} className="flex items-center space-x-2 w-full md:w-auto">
          <div className="relative flex-1 md:w-64">
            <Search className="w-4 h-4 text-slate-500 absolute left-3 top-1/2 -translate-y-1/2" />
            <input
              type="text"
              value={seqInput}
              onChange={(e) => setSeqInput(e.target.value)}
              placeholder="Jump to sequence (e.g. 29)..."
              className="w-full bg-[#0B0F17] border border-slate-800 rounded-xl pl-9 pr-4 py-2 text-xs text-slate-200 placeholder-slate-500 focus:outline-none focus:border-violet-500 focus:ring-1 focus:ring-violet-500 font-mono transition-colors duration-150"
            />
          </div>
          <button
            type="submit"
            className="btn-press-sm px-3.5 py-2 bg-violet-600 hover:bg-violet-500 text-white rounded-xl text-xs font-semibold transition-colors duration-150 shadow-xs"
          >
            Jump
          </button>
          {activeAroundSeq && (
            <button
              type="button"
              onClick={handleJumpToHead}
              className="btn-press-sm px-3 py-2 bg-slate-800 hover:bg-slate-700 text-slate-300 rounded-xl text-xs font-medium border border-slate-700 transition-colors duration-150"
              title="Return to latest chain head"
            >
              Latest Head
            </button>
          )}
        </form>

        {/* Filters */}
        <div className="flex items-center space-x-3 w-full md:w-auto justify-end">
          <div className="flex items-center space-x-1.5">
            <Filter className="w-3.5 h-3.5 text-slate-400" />
            <select
              value={selectedTable}
              onChange={(e) => {
                setSelectedTable(e.target.value);
                setPageOffset(0);
              }}
              className="bg-[#0B0F17] border border-slate-800 rounded-xl px-3 py-2 text-xs text-slate-300 focus:outline-none focus:border-violet-500 font-mono transition-colors duration-150"
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
            className="bg-[#0B0F17] border border-slate-800 rounded-xl px-3 py-2 text-xs text-slate-300 focus:outline-none focus:border-violet-500 font-mono transition-colors duration-150"
          >
            <option value="">All Operations</option>
            <option value="INSERT">INSERT</option>
            <option value="UPDATE">UPDATE</option>
            <option value="DELETE">DELETE</option>
          </select>
        </div>
      </div>

      {/* Main Visualizer Area */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
        {/* Block Timeline List */}
        <div className={`space-y-3 ${selectedBlock ? 'lg:col-span-7' : 'lg:col-span-12'}`}>
          {isLoading ? (
            <div className="p-12 text-center bg-[#0F172A]/80 border border-slate-800/80 rounded-2xl">
              <RefreshCw className="w-6 h-6 text-violet-400 animate-fast-spin mx-auto mb-3" />
              <p className="text-xs text-slate-400 font-mono">Loading cryptographic chain blocks...</p>
            </div>
          ) : chainEntries.length === 0 ? (
            <div className="p-12 text-center bg-[#0F172A]/80 border border-slate-800/80 rounded-2xl">
              <GitBranch className="w-8 h-8 text-slate-500 mx-auto mb-3" />
              <p className="text-sm font-semibold text-slate-300">No chain entries found</p>
              <p className="text-xs text-slate-500 mt-1">Try broadening your search or resetting filters.</p>
            </div>
          ) : (
            <div className="space-y-3 relative before:absolute before:left-6 before:top-4 before:bottom-4 before:w-0.5 before:bg-slate-800/80">
              {chainEntries.map((entry, idx) => {
                const isTampered = incident.tamperedSeqId === entry.entry_id;
                const isSelected = selectedBlock?.entry_id === entry.entry_id;

                return (
                  <div
                    key={entry.entry_id}
                    onClick={() => setSelectedBlock(entry)}
                    className={`btn-press-sm relative ml-12 p-4 rounded-2xl border transition-colors duration-150 cursor-pointer group ${
                      isTampered
                        ? 'bg-rose-950/30 border-rose-500/70 shadow-md shadow-rose-950/40 hover:border-rose-400'
                        : isSelected
                        ? 'bg-violet-950/30 border-violet-500/80 shadow-xs'
                        : 'bg-[#0F172A]/80 border-slate-800/80 hover:border-slate-700 hover:bg-[#0F172A]'
                    }`}
                  >
                    {/* Node Dot on Connector Line */}
                    <div
                      className={`absolute -left-12 top-5 w-6 h-6 rounded-full border flex items-center justify-center transition-colors duration-150 ${
                        isTampered
                          ? 'bg-rose-500/20 border-rose-500 text-rose-400 shadow-[0_0_8px_rgba(244,63,94,0.8)]'
                          : isSelected
                          ? 'bg-violet-500/30 border-violet-400 text-violet-300'
                          : 'bg-[#0B0F17] border-slate-700 text-slate-400 group-hover:border-slate-500'
                      }`}
                    >
                      <span className="text-[10px] font-mono font-bold">{idx + 1}</span>
                    </div>

                    {/* Block Header */}
                    <div className="flex items-center justify-between gap-3">
                      <div className="flex items-center space-x-2.5">
                        <span className="text-xs font-mono font-extrabold text-slate-100 bg-slate-800/80 px-2.5 py-1 rounded-lg border border-slate-700/60">
                          #{entry.entry_id}
                        </span>
                        <span
                          className={`text-[10px] uppercase font-mono font-bold px-2 py-0.5 rounded-md border ${
                            OPERATION_STYLES[entry.operation]
                          }`}
                        >
                          {entry.operation}
                        </span>
                        <span className="text-xs font-mono text-slate-300 bg-[#0B0F17] px-2 py-0.5 rounded border border-slate-800">
                          {entry.table_name}
                        </span>
                        {isTampered && (
                          <span className="text-[10px] font-mono font-bold bg-rose-500/30 text-rose-200 border border-rose-500/50 px-2 py-0.5 rounded-md animate-pulse">
                            [TAMPERED]
                          </span>
                        )}
                      </div>

                      <div className="flex items-center space-x-2 text-xs text-slate-400">
                        <span className={`w-1.5 h-1.5 rounded-full ${SEVERITY_DOT[entry.severity]}`} />
                        <span className="font-mono text-[11px] text-slate-400">
                          {new Date(entry.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })}
                        </span>
                        <ChevronRight className="w-4 h-4 text-slate-500 group-hover:text-slate-300 transition-colors duration-150" />
                      </div>
                    </div>

                    {/* Hash linkage summary */}
                    <div className="mt-3 pt-3 border-t border-slate-800/80 grid grid-cols-1 sm:grid-cols-2 gap-3 text-xs font-mono">
                      <div>
                        <span className="text-[10px] text-slate-400 uppercase tracking-wider block mb-0.5">
                          Previous Hash
                        </span>
                        <span className="text-slate-400 bg-[#0B0F17] px-2 py-1 rounded border border-slate-800/80 block truncate">
                          {truncateHash(entry.prev_hash || '0000000000000000000000000000000000000000000000000000000000000000')}
                        </span>
                      </div>
                      <div>
                        <span className="text-[10px] text-slate-400 uppercase tracking-wider block mb-0.5">
                          Computed Entry Hash
                        </span>
                        <span
                          className={`px-2 py-1 rounded border block truncate font-semibold ${
                            isTampered
                              ? 'text-rose-300 bg-rose-950/40 border-rose-500/40'
                              : 'text-violet-300 bg-violet-950/30 border-violet-500/30'
                          }`}
                        >
                          {truncateHash(entry.hash)}
                        </span>
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          )}

          {/* Pagination Controls */}
          {!activeAroundSeq && chainEntries.length > 0 && (
            <div className="flex items-center justify-between pt-4 border-t border-slate-800/80">
              <button
                onClick={() => setPageOffset((prev) => Math.max(0, prev - PAGE_LIMIT))}
                disabled={pageOffset === 0 || isFetching}
                className="btn-press-sm px-4 py-2 bg-[#0F172A] border border-slate-800 hover:border-slate-700 text-slate-300 text-xs font-medium rounded-xl flex items-center space-x-1.5 transition-colors duration-150 disabled:opacity-40"
              >
                <ArrowLeft className="w-3.5 h-3.5" />
                <span>Newer Blocks</span>
              </button>
              <span className="text-xs text-slate-400 font-mono">
                Offset: {pageOffset} — {pageOffset + chainEntries.length}
              </span>
              <button
                onClick={() => setPageOffset((prev) => prev + PAGE_LIMIT)}
                disabled={chainEntries.length < PAGE_LIMIT || isFetching}
                className="btn-press-sm px-4 py-2 bg-[#0F172A] border border-slate-800 hover:border-slate-700 text-slate-300 text-xs font-medium rounded-xl flex items-center space-x-1.5 transition-colors duration-150 disabled:opacity-40"
              >
                <span>Older Blocks</span>
                <ArrowRight className="w-3.5 h-3.5" />
              </button>
            </div>
          )}
        </div>

        {/* Block Inspector Drawer / Card */}
        {selectedBlock && (
          <div className="lg:col-span-5 sticky top-6 bg-[#0F172A]/95 border border-violet-500/30 backdrop-blur-md rounded-2xl p-6 shadow-2xl shadow-violet-950/30 space-y-6 animate-drawer-in">
            {/* Header */}
            <div className="flex items-start justify-between border-b border-slate-800/80 pb-4">
              <div>
                <div className="flex items-center space-x-2">
                  <span className="text-xs font-mono font-bold uppercase tracking-wider text-violet-400">
                    Block Inspector
                  </span>
                  <span className="text-xs font-mono bg-violet-500/15 text-violet-300 px-2 py-0.5 rounded-md border border-violet-500/30">
                    #{selectedBlock.entry_id}
                  </span>
                </div>
                <h3 className="text-base font-bold text-slate-100 mt-1 flex items-center space-x-2">
                  <span>{selectedBlock.table_name}</span>
                  <span
                    className={`text-[10px] uppercase font-mono font-bold px-2 py-0.5 rounded-md border ${
                      OPERATION_STYLES[selectedBlock.operation]
                    }`}
                  >
                    {selectedBlock.operation}
                  </span>
                </h3>
              </div>
              <button
                onClick={() => setSelectedBlock(null)}
                className="btn-press-sm text-slate-400 hover:text-slate-200 p-1.5 rounded-lg hover:bg-slate-800 transition-colors duration-150"
                title="Close drawer"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            {/* Cryptographic Linkage Details */}
            <div className="space-y-3">
              <h4 className="text-xs font-semibold text-slate-300 uppercase tracking-wider flex items-center space-x-1.5">
                <Hash className="w-3.5 h-3.5 text-violet-400" />
                <span>Cryptographic Proof</span>
              </h4>

              <div className="bg-[#0B0F17] rounded-xl p-3.5 border border-slate-800 space-y-3 font-mono text-xs">
                <div>
                  <div className="flex items-center justify-between text-slate-400 text-[11px] mb-1">
                    <span>Entry Hash (H_i)</span>
                    <button
                      onClick={() => handleCopy(selectedBlock.hash, 'entry_hash')}
                      className="btn-press-sm text-violet-400 hover:text-violet-300 flex items-center space-x-1 text-[10px]"
                    >
                      {copiedHash === 'entry_hash' ? <Check className="w-3 h-3 text-emerald-400" /> : <Copy className="w-3 h-3" />}
                      <span>{copiedHash === 'entry_hash' ? 'Copied' : 'Copy'}</span>
                    </button>
                  </div>
                  <div className="text-slate-200 break-all bg-[#0F172A] p-2 rounded border border-slate-800 text-[11px]">
                    {selectedBlock.hash}
                  </div>
                </div>

                <div>
                  <div className="flex items-center justify-between text-slate-400 text-[11px] mb-1">
                    <span>Previous Hash (H_{'{i-1}'})</span>
                    <button
                      onClick={() => handleCopy(selectedBlock.prev_hash || '', 'prev_hash')}
                      className="btn-press-sm text-violet-400 hover:text-violet-300 flex items-center space-x-1 text-[10px]"
                    >
                      {copiedHash === 'prev_hash' ? <Check className="w-3 h-3 text-emerald-400" /> : <Copy className="w-3 h-3" />}
                      <span>{copiedHash === 'prev_hash' ? 'Copied' : 'Copy'}</span>
                    </button>
                  </div>
                  <div className="text-slate-400 break-all bg-[#0F172A] p-2 rounded border border-slate-800 text-[11px]">
                    {selectedBlock.prev_hash || '0'.repeat(64)}
                  </div>
                </div>

                <div className="pt-2 border-t border-slate-800/80 text-[11px] text-slate-400">
                  <span>Formula: </span>
                  <code className="text-violet-300">H_i = SHA-256(Canonical(R_i) || H_{'{i-1}'})</code>
                </div>
              </div>
            </div>

            {/* Event Metadata */}
            <div className="grid grid-cols-2 gap-3 text-xs bg-[#0B0F17] p-3 rounded-xl border border-slate-800/80">
              <div>
                <span className="text-[10px] text-slate-400 uppercase tracking-wider block">Actor</span>
                <span className="text-slate-200 font-medium truncate block">{selectedBlock.actor_email}</span>
                <span className="text-[10px] text-slate-500 font-mono">({selectedBlock.actor_role})</span>
              </div>
              <div>
                <span className="text-[10px] text-slate-400 uppercase tracking-wider block">Recorded At</span>
                <span className="text-slate-200 font-mono text-[11px] block">
                  {new Date(selectedBlock.timestamp).toLocaleString()}
                </span>
              </div>
            </div>

            {/* Field Diff Viewer */}
            <div className="space-y-2">
              <h4 className="text-xs font-semibold text-slate-300 uppercase tracking-wider flex items-center space-x-1.5">
                <Database className="w-3.5 h-3.5 text-violet-400" />
                <span>Field-Level Payload Diff</span>
              </h4>
              <div className="bg-[#0B0F17] border border-slate-800 rounded-xl p-3 max-h-72 overflow-y-auto">
                <DiffViewer
                  oldValue={selectedBlock.old_value}
                  newValue={selectedBlock.new_value}
                  operation={selectedBlock.operation}
                />
              </div>
            </div>

            {/* Action CTAs: Deep-link to Time Travel or Audit Log */}
            <div className="pt-2 border-t border-slate-800/80 flex flex-col sm:flex-row gap-2">
              {/* Extract employee_id if present */}
              {(() => {
                const empId =
                  (selectedBlock.new_value as any)?.employee_id ||
                  (selectedBlock.old_value as any)?.employee_id ||
                  (selectedBlock.new_value as any)?.id;

                return (
                  <button
                    onClick={() => {
                      const params = new URLSearchParams();
                      if (empId) params.set('emp_id', String(empId));
                      params.set('as_of', selectedBlock.timestamp);
                      navigate(`/auditor/time-travel?${params.toString()}`);
                    }}
                    className="btn-press-sm flex-1 px-3 py-2 bg-indigo-600/20 hover:bg-indigo-600/30 border border-indigo-500/40 text-indigo-200 text-xs font-semibold rounded-xl flex items-center justify-center space-x-1.5 transition-colors duration-150 shadow-xs"
                  >
                    <Clock className="w-3.5 h-3.5 text-indigo-400" />
                    <span>Time-Travel State ⏱</span>
                  </button>
                );
              })()}

              <button
                onClick={() => navigate(`/auditor/log?seq=${selectedBlock.entry_id}`)}
                className="btn-press-sm flex-1 px-3 py-2 bg-[#0F172A] hover:bg-slate-800 border border-slate-800 text-slate-200 text-xs font-medium rounded-xl flex items-center justify-center space-x-1.5 transition-colors duration-150"
              >
                <ExternalLink className="w-3.5 h-3.5 text-slate-400" />
                <span>View in Audit Log</span>
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
