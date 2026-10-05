import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { useAuth } from '@clerk/clerk-react';
import AnchorStatus from '../../components/auditor/AnchorStatus';
import ChainVisualization from '../../components/auditor/ChainVisualization';
import VerificationControl from '../../components/auditor/VerificationControl';
import ExportControl from '../../components/auditor/ExportControl';
import {
  fetchAuditChain,
  fetchAnchorStatus,
  fetchSuspiciousFlags,
  SUSPICIOUS_FLAGS_QUERY_KEY,
  type SuspiciousFlagItem,
} from '../../services/auditService';
import { AlertTriangle, ArrowRight, Loader2, RefreshCw } from 'lucide-react';
import { Link } from 'react-router-dom';
import PageHeader from '../../components/common/PageHeader';

export default function AuditorOverview() {
  const { getToken } = useAuth();
  const [tamperedSeqId, setTamperedSeqId] = useState<number | null>(null);

  const {
    data: chainEntries = [],
    isLoading: isChainLoading,
    isError: isChainError,
    refetch: refetchChain,
  } = useQuery({
    queryKey: ['audit-chain', tamperedSeqId],
    queryFn: () =>
      fetchAuditChain(
        getToken,
        tamperedSeqId ? { around_seq: tamperedSeqId, limit: 12 } : { limit: 10 }
      ),
    refetchInterval: 2500,
  });

  const {
    data: anchorData,
    isLoading: isAnchorLoading,
    isError: isAnchorError,
    refetch: refetchAnchor,
  } = useQuery({
    queryKey: ['anchor-status'],
    queryFn: () => fetchAnchorStatus(getToken),
    refetchInterval: 4000,
  });

  const {
    data: suspiciousFlags,
    isLoading: isRiskLoading,
    isError: isRiskError,
  } = useQuery<SuspiciousFlagItem[]>({
    queryKey: SUSPICIOUS_FLAGS_QUERY_KEY,
    queryFn: () => fetchSuspiciousFlags(getToken),
    refetchInterval: 5000,
  });
  const pendingRiskCount = suspiciousFlags?.filter((flag) => !flag.reviewed_at).length ?? 0;

  return (
    <div className="space-y-6">
      <PageHeader
        title="Integrity Overview"
        description="Verification, external anchoring, and recent audit-chain activity."
      />
      {/* Integrity checks get the working width; evidence export sits in its own compact action row. */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-5 items-start">
        <div className="animate-fade-cascade stagger-1 min-w-0">
          <VerificationControl onResult={(res) => setTamperedSeqId(res.tampered_sequence_id)} />
        </div>
        {isAnchorLoading ? (
          <div className="animate-fade-cascade stagger-2 rounded-2xl border border-linear-hairline bg-linear-surface-1 p-5 flex flex-col items-center justify-center min-h-[220px]">
            <Loader2 className="w-6 h-6 text-linear-primary animate-fast-spin mb-2" />
            <span className="text-sm text-linear-ink-subtle">Loading anchor status…</span>
          </div>
        ) : isAnchorError || !anchorData ? (
          <section className="animate-fade-cascade stagger-2 rounded-2xl border border-status-warning/35 bg-linear-surface-1 p-5 flex items-center gap-4 min-h-[220px]" role="alert">
            <div className="w-10 h-10 rounded-lg border border-status-warning/30 bg-status-warning/10 text-status-warning flex items-center justify-center shrink-0">
              <AlertTriangle className="w-5 h-5" />
            </div>
            <div className="min-w-0">
              <h2 className="text-sm font-semibold text-linear-ink">Anchor status unavailable</h2>
              <p className="mt-1 text-sm leading-5 text-linear-ink-muted">Argus could not retrieve the latest checkpoint state. Integrity has not been confirmed.</p>
              <button type="button" onClick={() => void refetchAnchor()} className="mt-3 inline-flex items-center gap-2 text-sm font-medium text-linear-primary hover:text-linear-primary-hover focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-linear-primary rounded">
                <RefreshCw className="w-3.5 h-3.5" /> Retry
              </button>
            </div>
          </section>
        ) : (
          <div className="animate-fade-cascade stagger-2 min-w-0">
            <AnchorStatus data={anchorData} />
          </div>
        )}
      </div>
      <div className="animate-fade-cascade stagger-3 min-w-0">
          <ExportControl />
      </div>

      {/* Main content: Chain view (75% width) + suspicious flags (25% width) */}
      <div className="grid grid-cols-1 xl:grid-cols-12 gap-6 items-start">
        {/* Chain visualization — 75% width (extended to eliminate horizontal scrollbar) */}
        <div className="xl:col-span-9 min-w-0 space-y-2 animate-fade-cascade stagger-4">
          <div className="flex items-center justify-between px-1">
            <span className="text-xs font-mono font-medium text-linear-ink-subtle">
              {tamperedSeqId ? `Focused window around violation #${tamperedSeqId}` : 'Recent Chain Blocks (Tail)'}
            </span>
            <Link
              to={`/auditor/chain${tamperedSeqId ? `?seq=${tamperedSeqId}` : ''}`}
              className="text-xs text-linear-primary hover:text-linear-primary-hover flex items-center space-x-1 font-medium transition-colors duration-150 group focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-linear-primary rounded px-1"
            >
              <span>Full Chain Explorer</span>
              <ArrowRight className="w-3.5 h-3.5 transition-transform duration-150 group-hover:translate-x-0.5" />
            </Link>
          </div>
          {isChainLoading && chainEntries.length === 0 ? (
            <div className="bg-linear-surface-1 border border-linear-hairline rounded-2xl p-12 flex flex-col items-center justify-center">
              <Loader2 className="w-6 h-6 text-linear-primary animate-fast-spin mb-2" />
              <span className="text-sm text-linear-ink-subtle">Loading hash chain…</span>
            </div>
          ) : isChainError && chainEntries.length === 0 ? (
            <section className="bg-linear-surface-1 border border-status-warning/35 rounded-2xl p-6 flex items-center gap-4" role="alert">
              <AlertTriangle className="w-5 h-5 text-status-warning shrink-0" />
              <div className="min-w-0">
                <h2 className="text-sm font-semibold text-linear-ink">Chain entries unavailable</h2>
                <p className="mt-1 text-sm text-linear-ink-muted">The audit service did not return chain records. No empty or healthy state is inferred.</p>
              </div>
              <button type="button" onClick={() => void refetchChain()} className="ml-auto shrink-0 inline-flex items-center gap-2 text-sm font-medium text-linear-primary hover:text-linear-primary-hover focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-linear-primary rounded">
                <RefreshCw className="w-3.5 h-3.5" /> Retry
              </button>
            </section>
          ) : (
            <ChainVisualization entries={chainEntries} tamperedSequenceId={tamperedSeqId} />
          )}
        </div>

        {/* Suspicious flags link panel — 25% viewport anchored */}
        <div className="xl:col-span-3 animate-fade-cascade stagger-5 bg-linear-surface-1 border border-linear-hairline hover:border-linear-hairline-strong rounded-2xl overflow-hidden flex flex-col items-center p-6 text-center relative group shadow-sm xl:sticky xl:top-6 self-start transition-all duration-200">
          <div className="w-14 h-14 rounded-2xl bg-linear-surface-2 border border-linear-hairline flex items-center justify-center mb-5 group-hover:border-linear-primary/40 transition-colors duration-200">
            <AlertTriangle className="w-7 h-7 text-linear-primary/80 group-hover:text-linear-primary transition-colors duration-150" />
          </div>
          <span className="text-[10px] font-mono uppercase tracking-widest text-linear-primary font-semibold mb-1">
            Forensic Incident Queue
          </span>
          <h3 className="text-lg font-semibold text-linear-ink tracking-tight">Activity & Risk Engine</h3>
          <p className="text-sm text-linear-ink-subtle mt-2 mb-6 max-w-xs leading-relaxed">
            Review trigger-flagged events, unauthorized mutations, and automated compliance alerts.
          </p>
          <div className="mb-5 min-h-10" role="status" aria-live="polite">
            {isRiskLoading ? (
              <span className="text-xs text-linear-ink-muted">Loading risk status…</span>
            ) : isRiskError ? (
              <span className="inline-flex items-center gap-1.5 text-xs font-medium text-status-warning">
                <AlertTriangle className="h-3.5 w-3.5" /> Pending risk count unavailable
              </span>
            ) : (
              <span className={`inline-flex items-center gap-2 rounded-full px-2.5 py-1 text-xs font-semibold ${pendingRiskCount > 0 ? 'bg-status-warning/10 text-status-warning' : 'bg-linear-success/10 text-linear-success'}`}>
                <span className={`h-1.5 w-1.5 rounded-full ${pendingRiskCount > 0 ? 'bg-status-warning' : 'bg-linear-success'}`} />
                {pendingRiskCount} pending {pendingRiskCount === 1 ? 'flag' : 'flags'}
              </span>
            )}
          </div>
          <Link
            to="/auditor/activity"
            className="w-full inline-flex items-center justify-center space-x-2 bg-linear-primary hover:bg-linear-primary-hover text-white font-medium px-5 py-2.5 rounded-xl transition-all duration-150 shadow-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-linear-primary focus-visible:ring-offset-2 focus-visible:ring-offset-linear-canvas active:scale-[0.985]"
          >
            <span>Open Risk Panel</span>
            <ArrowRight className="w-4 h-4" />
          </Link>
        </div>
      </div>
    </div>
  );
}
