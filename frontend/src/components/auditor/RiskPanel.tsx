import { useState } from 'react';
import { Link } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useAuth } from '@clerk/clerk-react';
import { AlertTriangle, CheckCircle2, ShieldAlert, ArrowUpRight, GitCommit } from 'lucide-react';
import { fetchSuspiciousFlags, reviewSuspiciousFlag, SuspiciousFlagItem } from '../../services/auditService';

export default function RiskPanel() {
  const { getToken } = useAuth();
  const queryClient = useQueryClient();
  const [filter, setFilter] = useState<'all' | 'unreviewed'>('unreviewed');

  const { data: flags = [], isLoading, isError } = useQuery<SuspiciousFlagItem[]>({
    queryKey: ['suspiciousFlags'],
    queryFn: () => fetchSuspiciousFlags(() => getToken()),
    refetchInterval: 3000,
  });

  const reviewMutation = useMutation({
    mutationFn: (flagId: number) => reviewSuspiciousFlag(flagId, () => getToken()),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['suspiciousFlags'] });
    },
  });

  const filteredFlags = flags.filter((f) => (filter === 'unreviewed' ? !f.reviewed_at : true));
  const unreviewedCount = flags.filter((f) => !f.reviewed_at).length;

  if (isLoading) {
    return (
      <div className="flex justify-center items-center h-64 border border-slate-800/80 rounded-2xl bg-[#0F172A]/80">
        <div className="animate-fast-spin rounded-full h-8 w-8 border-2 border-violet-500/30 border-t-violet-400"></div>
      </div>
    );
  }

  if (isError) {
    return (
      <div className="flex flex-col items-center justify-center h-64 border border-rose-500/25 rounded-2xl bg-rose-500/10 text-rose-400 p-6 text-center">
        <AlertTriangle className="w-10 h-10 mb-3 opacity-80" />
        <p className="font-semibold">Failed to load risk data</p>
        <p className="text-sm mt-1 opacity-70">Could not communicate with the audit engine.</p>
      </div>
    );
  }

  return (
    <div className="space-y-6 animate-fade-cascade">
      
      {/* Header and Stats */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        <div className="md:col-span-2 bg-[#0F172A]/80 border border-slate-800/80 rounded-2xl p-6 flex flex-col justify-center relative overflow-hidden shadow-sm">
          {/* Background glow */}
          <div className="absolute -top-24 -right-24 w-64 h-64 bg-violet-600/10 blur-[80px] rounded-full pointer-events-none" />
          
          <h2 className="text-xl font-bold text-slate-100 flex items-center space-x-2">
            <ShieldAlert className="w-6 h-6 text-violet-400" />
            <span>Activity & Risk Panel</span>
          </h2>
          <p className="text-slate-400 text-sm mt-2 max-w-xl">
            Automatically flagged events from database triggers. Flags highlight potential compliance violations, off-hours access, or abnormal mutation rates.
          </p>
        </div>

        <div className="bg-[#0F172A]/80 border border-slate-800/80 rounded-2xl p-6 flex items-center justify-between shadow-sm">
          <div>
            <p className="text-sm font-medium text-slate-400">Action Required</p>
            <div className="mt-2 flex items-baseline space-x-2">
              <span className={`text-4xl font-black tracking-tight font-mono ${unreviewedCount > 0 ? 'text-amber-400' : 'text-emerald-400'}`}>
                {unreviewedCount}
              </span>
              <span className="text-sm text-slate-500 font-medium">unreviewed flags</span>
            </div>
          </div>
          <div className={`p-4 rounded-full ${unreviewedCount > 0 ? 'bg-amber-400/10' : 'bg-emerald-400/10'}`}>
            <AlertTriangle className={`w-8 h-8 ${unreviewedCount > 0 ? 'text-amber-400' : 'text-emerald-400'}`} />
          </div>
        </div>
      </div>

      {/* Main Panel */}
      <div className="bg-[#0F172A]/80 border border-slate-800/80 rounded-2xl overflow-hidden shadow-sm">
        
        {/* Toolbar */}
        <div className="px-6 py-4 border-b border-slate-800/80 flex flex-col sm:flex-row sm:items-center justify-between gap-4 bg-[#0B0F17]/50">
          <h3 className="text-base font-semibold text-slate-100">Flagged Events</h3>
          <div className="flex bg-[#0B0F17] p-1 rounded-xl border border-slate-800 self-start sm:self-auto">
            <button
              onClick={() => setFilter('unreviewed')}
              className={`btn-press-sm px-3 py-1.5 text-xs font-semibold rounded-lg transition-colors duration-150 ${
                filter === 'unreviewed' ? 'bg-violet-600 text-white shadow-xs' : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              Unreviewed ({unreviewedCount})
            </button>
            <button
              onClick={() => setFilter('all')}
              className={`btn-press-sm px-3 py-1.5 text-xs font-semibold rounded-lg transition-colors duration-150 ${
                filter === 'all' ? 'bg-violet-600 text-white shadow-xs' : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              All Flags
            </button>
          </div>
        </div>

        {/* Flag List */}
        <div className="divide-y divide-slate-800/60 min-h-[400px]">
          {filteredFlags.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-24 text-slate-500">
              <CheckCircle2 className="w-12 h-12 text-emerald-500/40 mb-4" />
              <p className="text-sm font-medium text-slate-300">No {filter === 'unreviewed' ? 'unreviewed' : ''} flags found.</p>
              <p className="text-xs mt-1 text-slate-400">The system is currently operating within normal parameters.</p>
            </div>
          ) : (
            filteredFlags.map((flag) => (
              <div key={flag.flag_id} className={`p-6 flex flex-col md:flex-row gap-6 transition-colors duration-150 ${flag.reviewed_at ? 'bg-[#0B0F17]/30 opacity-75' : 'hover:bg-[#0B0F17]/40'}`}>
                
                {/* Left col: Status & Indicator */}
                <div className="flex-shrink-0 flex items-start space-x-4 md:w-48">
                  <div className="mt-1 flex-shrink-0">
                    {flag.reviewed_at ? (
                      <CheckCircle2 className="w-5 h-5 text-emerald-500" />
                    ) : (
                      <div className="relative">
                        <div className="absolute inset-0 bg-amber-400/40 rounded-full blur-[4px] animate-pulse"></div>
                        <AlertTriangle className="w-5 h-5 text-amber-400 relative z-10" />
                      </div>
                    )}
                  </div>
                  <div>
                    <span className="text-xs font-bold uppercase tracking-wider text-slate-400">Flag ID</span>
                    <p className="text-sm font-mono text-slate-200 mt-0.5">#{flag.flag_id}</p>
                    <p className="text-[11px] text-slate-400 mt-2 font-mono">
                      {new Date(flag.created_at).toLocaleString()}
                    </p>
                  </div>
                </div>

                {/* Middle col: Reason & Context */}
                <div className="flex-grow min-w-0">
                  <div className="flex flex-col justify-center h-full">
                    <p className="text-sm text-slate-200 font-medium leading-relaxed">
                      {flag.flag_reason}
                    </p>
                    <div className="mt-3 flex items-center space-x-3 text-xs">
                      <Link
                        to={`/auditor/chain?seq=${flag.audit_log_sequence_id}`}
                        className="btn-press-sm text-slate-400 hover:text-violet-300 flex items-center bg-[#0B0F17] hover:bg-slate-800 px-2.5 py-1 rounded-md border border-slate-800 transition-colors duration-150 group"
                        title="Inspect Block in Chain Explorer"
                      >
                        <span>Audit Seq:</span>
                        <span className="font-mono text-violet-400 group-hover:underline ml-1">#{flag.audit_log_sequence_id}</span>
                        <ArrowUpRight className="w-3 h-3 ml-1 text-slate-500 group-hover:text-violet-400 transition-transform duration-150" />
                      </Link>
                      {flag.reviewed_at && (
                        <span className="text-emerald-400/80 flex items-center">
                          <CheckCircle2 className="w-3.5 h-3.5 mr-1" />
                          Reviewed by User {flag.reviewed_by}
                        </span>
                      )}
                    </div>
                  </div>
                </div>

                {/* Right col: Actions */}
                <div className="flex-shrink-0 flex flex-col md:w-36 gap-2 pt-2 md:pt-0">
                  {!flag.reviewed_at ? (
                    <>
                      <button
                        onClick={() => reviewMutation.mutate(flag.flag_id)}
                        disabled={reviewMutation.isPending}
                        className="btn-press-sm flex items-center justify-center space-x-1.5 w-full bg-violet-600 hover:bg-violet-500 text-white text-xs font-semibold py-2 px-3 rounded-lg transition-colors duration-150 shadow-[0_0_15px_rgba(124,58,237,0.3)] disabled:opacity-50 disabled:cursor-not-allowed"
                      >
                        {reviewMutation.isPending && reviewMutation.variables === flag.flag_id ? (
                          <div className="w-3 h-3 border-2 border-white/30 border-t-white rounded-full animate-fast-spin" />
                        ) : (
                          <CheckCircle2 className="w-4 h-4" />
                        )}
                        <span>Mark Safe</span>
                      </button>
                      <div className="flex items-center gap-1.5">
                        <Link
                          to={`/auditor/chain?seq=${flag.audit_log_sequence_id}`}
                          className="btn-press-sm flex-1 flex items-center justify-center space-x-1 bg-[#0B0F17] hover:bg-slate-800 text-slate-300 text-[11px] py-1.5 px-2 rounded-md border border-slate-800 transition-colors duration-150"
                          title="Inspect in Chain Explorer"
                        >
                          <GitCommit className="w-3 h-3 text-violet-400" />
                          <span>Chain</span>
                        </Link>
                        <Link
                          to={`/auditor/log?seq=${flag.audit_log_sequence_id}`}
                          className="btn-press-sm flex-1 flex items-center justify-center space-x-1 bg-[#0B0F17] hover:bg-slate-800 text-slate-300 text-[11px] py-1.5 px-2 rounded-md border border-slate-800 transition-colors duration-150"
                          title="View in Audit Log"
                        >
                          <span>Log</span>
                          <ArrowUpRight className="w-3 h-3 text-slate-400" />
                        </Link>
                      </div>
                    </>
                  ) : (
                    <div className="flex items-center gap-1.5 w-full">
                      <Link
                        to={`/auditor/chain?seq=${flag.audit_log_sequence_id}`}
                        className="btn-press-sm flex-1 flex items-center justify-center space-x-1 bg-[#0B0F17] hover:bg-slate-800 text-slate-300 text-[11px] py-1.5 px-2 rounded-md border border-slate-800 transition-colors duration-150"
                        title="Inspect in Chain Explorer"
                      >
                        <GitCommit className="w-3 h-3 text-violet-400" />
                        <span>Chain</span>
                      </Link>
                      <Link
                        to={`/auditor/log?seq=${flag.audit_log_sequence_id}`}
                        className="btn-press-sm flex-1 flex items-center justify-center space-x-1 bg-[#0B0F17] hover:bg-slate-800 text-slate-300 text-[11px] py-1.5 px-2 rounded-md border border-slate-800 transition-colors duration-150"
                        title="View in Audit Log"
                      >
                        <span>View Log</span>
                        <ArrowUpRight className="w-3 h-3 text-slate-400" />
                      </Link>
                    </div>
                  )}
                </div>

              </div>
            ))
          )}
        </div>
      </div>
    </div>
  );
}
