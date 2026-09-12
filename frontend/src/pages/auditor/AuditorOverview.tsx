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

  const {
    data: chainEntries = [],
    isLoading: isChainLoading,
  } = useQuery({
    queryKey: ['audit-chain'],
    queryFn: () => fetchAuditChain(getToken, 10),
    refetchInterval: 10000,
  });

  const {
    data: anchorData,
    isLoading: isAnchorLoading,
  } = useQuery({
    queryKey: ['anchor-status'],
    queryFn: () => fetchAnchorStatus(getToken),
    refetchInterval: 15000,
  });

  return (
    <div className="animate-in fade-in slide-in-from-bottom-4 duration-500 space-y-6">

      {/* Top row: VerificationControl, AnchorStatus, and ExportControl */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <VerificationControl />
        {isAnchorLoading ? (
          <div className="rounded-2xl border border-slate-700/50 bg-slate-900/50 p-5 flex flex-col items-center justify-center min-h-[220px]">
            <Loader2 className="w-6 h-6 text-violet-400 animate-spin mb-2" />
            <span className="text-xs text-slate-500 font-mono">Syncing anchor status...</span>
          </div>
        ) : (
          <AnchorStatus data={anchorData ?? DEFAULT_ANCHOR} />
        )}
        <ExportControl />
      </div>

      {/* Main content: Chain view + suspicious flags */}
      <div className="grid grid-cols-1 xl:grid-cols-3 gap-6">
        {/* Chain visualization — 2/3 width */}
        <div className="xl:col-span-2">
          {isChainLoading && chainEntries.length === 0 ? (
            <div className="bg-slate-900/50 border border-slate-700/50 rounded-2xl p-12 flex flex-col items-center justify-center">
              <Loader2 className="w-6 h-6 text-violet-400 animate-spin mb-2" />
              <span className="text-xs text-slate-500 font-mono">Loading hash chain...</span>
            </div>
          ) : (
            <ChainVisualization entries={chainEntries} />
          )}
        </div>

        {/* Suspicious flags link panel — 1/3 */}
        <div className="bg-slate-900/50 border border-slate-700/50 rounded-2xl overflow-hidden flex flex-col justify-center items-center p-8 text-center relative group">
          <div className="absolute inset-0 bg-gradient-to-br from-violet-600/5 to-transparent pointer-events-none" />
          <AlertTriangle className="w-12 h-12 text-violet-400/80 mb-4 group-hover:text-violet-400 transition-colors" />
          <h3 className="text-lg font-semibold text-slate-200">Activity & Risk</h3>
          <p className="text-sm text-slate-400 mt-2 mb-6">
            Review automatically flagged events and compliance violations.
          </p>
          <Link
            to="/auditor/activity"
            className="inline-flex items-center space-x-2 bg-violet-600 hover:bg-violet-500 text-white font-medium px-5 py-2.5 rounded-lg transition-all shadow-[0_0_15px_rgba(124,58,237,0.3)] hover:shadow-[0_0_20px_rgba(124,58,237,0.5)]"
          >
            <span>Open Risk Panel</span>
            <ArrowRight className="w-4 h-4" />
          </Link>
        </div>
      </div>
    </div>
  );
}
