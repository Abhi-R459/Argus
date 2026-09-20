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
  type AnchorInfo,
} from '../../services/auditService';
import { AlertTriangle, ArrowRight, Loader2 } from 'lucide-react';
import { Link } from 'react-router-dom';

const DEFAULT_ANCHOR: AnchorInfo = {
  status: 'ANCHORED',
  anchor_store: 'local_file',
  anchor_location: './anchor/chain_anchor.log',
  last_anchored: new Date().toISOString(),
  anchor_hash: 'sha256:0000000000000000000000000000000000000000000000000000000000000000',
  entries_since_anchor: 0,
};

export default function AuditorOverview() {
  const { getToken } = useAuth();
  const [tamperedSeqId, setTamperedSeqId] = useState<number | null>(null);

  const {
    data: chainEntries = [],
    isLoading: isChainLoading,
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
  } = useQuery({
    queryKey: ['anchor-status'],
    queryFn: () => fetchAnchorStatus(getToken),
    refetchInterval: 4000,
  });

  return (
    <div className="space-y-6">

      {/* Top row: VerificationControl, AnchorStatus, and ExportControl */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="animate-fade-cascade stagger-1">
          <VerificationControl onResult={(res) => setTamperedSeqId(res.tampered_sequence_id)} />
        </div>
        {isAnchorLoading ? (
          <div className="animate-fade-cascade stagger-2 rounded-2xl border border-linear-hairline bg-linear-surface-1 p-5 flex flex-col items-center justify-center min-h-[220px]">
            <Loader2 className="w-6 h-6 text-linear-primary animate-fast-spin mb-2" />
            <span className="text-xs text-linear-ink-subtle font-mono">Syncing anchor status...</span>
          </div>
        ) : (
          <div className="animate-fade-cascade stagger-2">
            <AnchorStatus data={anchorData ?? DEFAULT_ANCHOR} />
          </div>
        )}
        <div className="animate-fade-cascade stagger-3">
          <ExportControl />
        </div>
      </div>

      {/* Main content: Chain view + suspicious flags */}
      <div className="grid grid-cols-1 xl:grid-cols-3 gap-6 items-start">
        {/* Chain visualization — 2/3 width */}
        <div className="xl:col-span-2 min-w-0 space-y-2 animate-fade-cascade stagger-4">
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
              <span className="text-xs text-linear-ink-subtle font-mono">Loading hash chain...</span>
            </div>
          ) : (
            <ChainVisualization entries={chainEntries} tamperedSequenceId={tamperedSeqId} />
          )}
        </div>

        {/* Suspicious flags link panel — 1/3 viewport anchored */}
        <div className="animate-fade-cascade stagger-5 bg-linear-surface-1 border border-linear-hairline hover:border-linear-hairline-strong rounded-2xl overflow-hidden flex flex-col items-center p-8 text-center relative group shadow-sm xl:sticky xl:top-6 self-start transition-all duration-200">
          <div className="absolute inset-0 bg-gradient-to-br from-linear-primary/5 via-transparent to-transparent pointer-events-none" />
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
