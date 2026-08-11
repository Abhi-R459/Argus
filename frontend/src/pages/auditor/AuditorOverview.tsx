import AnchorStatus from '../../components/auditor/AnchorStatus';
import ChainVisualization from '../../components/auditor/ChainVisualization';
import VerificationControl from '../../components/auditor/VerificationControl';
import {
  getAuditChain,
  getAnchorStatus,
  getSuspiciousFlags,
} from '../../services/mockAuditService';
import { AlertTriangle, Eye } from 'lucide-react';

export default function AuditorOverview() {
  // Chain entries and anchor still from mock — real endpoints come in Weeks 7–8 (INT-004, INT-005)
  const chainEntries = getAuditChain(10);
  const anchorData   = getAnchorStatus();
  const flags        = getSuspiciousFlags();

  return (
    <div className="animate-in fade-in slide-in-from-bottom-4 duration-500 space-y-6">

      {/* Top row: VerificationControl (real API) + AnchorStatus (mocked) */}
      <div className="grid grid-cols-1 xl:grid-cols-2 gap-6">
        {/* VerificationControl calls POST /api/verify for real */}
        <VerificationControl />

        {/* AnchorStatus still mocked — real endpoint lands Week 7 */}
        <AnchorStatus data={anchorData} />
      </div>

      {/* Main content: Chain view + suspicious flags */}
      <div className="grid grid-cols-1 xl:grid-cols-3 gap-6">
        {/* Chain visualization — 2/3 width */}
        <div className="xl:col-span-2">
          <ChainVisualization entries={chainEntries} />
        </div>

        {/* Suspicious flags mini-panel — 1/3 */}
        <div className="bg-slate-900/50 border border-slate-700/50 rounded-2xl overflow-hidden">
          <div className="flex items-center justify-between px-5 py-3.5 border-b border-slate-700/50 bg-slate-900/30">
            <div className="flex items-center space-x-2">
              <AlertTriangle className="w-4 h-4 text-amber-400" />
              <h3 className="text-sm font-semibold text-slate-200">Suspicious Activity</h3>
            </div>
            {flags.filter((f) => !f.reviewed).length > 0 && (
              <span className="text-xs bg-red-500/20 text-red-300 border border-red-500/25 px-2 py-0.5 rounded-full font-bold">
                {flags.filter((f) => !f.reviewed).length} unreviewed
              </span>
            )}
          </div>

          <div className="divide-y divide-slate-800/60">
            {flags.length === 0 ? (
              <div className="px-5 py-8 text-center text-slate-600 text-sm">No active flags</div>
            ) : (
              flags.map((flag) => (
                <div
                  key={flag.flag_id}
                  className="px-5 py-3.5 flex items-start space-x-3 hover:bg-slate-800/30 transition-colors"
                >
                  <div
                    className={`mt-0.5 w-2 h-2 rounded-full flex-shrink-0 ${
                      flag.severity === 'critical'
                        ? 'bg-red-500 shadow-[0_0_6px_rgba(239,68,68,0.7)]'
                        : 'bg-amber-400'
                    }`}
                  />
                  <div className="min-w-0">
                    <p className="text-xs font-semibold text-slate-300 truncate">
                      {flag.employee_name}
                    </p>
                    <p className="text-[11px] text-slate-500 mt-0.5 leading-snug">{flag.reason}</p>
                    <p className="text-[10px] text-slate-600 mt-1">
                      {new Date(flag.flagged_at).toLocaleString()}
                    </p>
                  </div>
                  <button
                    id={`flag-review-${flag.flag_id}`}
                    className="flex-shrink-0 flex items-center space-x-1 text-[10px] text-violet-400 hover:text-violet-300 border border-violet-500/20 hover:border-violet-500/40 px-2 py-1 rounded-lg transition-colors bg-violet-500/5 hover:bg-violet-500/10"
                  >
                    <Eye className="w-3 h-3" />
                    <span>Review</span>
                  </button>
                </div>
              ))
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
