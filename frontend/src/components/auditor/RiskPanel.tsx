import { useState } from 'react';
import { Link } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useAuth } from '@clerk/clerk-react';
import { AlertTriangle, CheckCircle2, ShieldAlert, ArrowUpRight, GitCommit } from 'lucide-react';
import { fetchSuspiciousFlags, reviewSuspiciousFlag, SuspiciousFlagItem } from '../../services/auditService';
import Button from '../common/Button';

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
      <div className="flex justify-center items-center h-64 border border-linear-hairline rounded-2xl bg-linear-surface-1">
        <div className="animate-fast-spin rounded-full h-8 w-8 border-2 border-linear-primary/30 border-t-linear-primary"></div>
      </div>
    );
  }

  if (isError) {
    return (
      <div className="flex flex-col items-center justify-center h-64 border border-grafana-orange/30 rounded-2xl bg-grafana-orange/10 text-grafana-orange p-6 text-center">
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
        <div className="md:col-span-2 bg-linear-surface-1 border border-linear-hairline rounded-2xl p-6 flex flex-col justify-center relative overflow-hidden shadow-sm">
          <h2 className="text-xl font-bold text-linear-ink flex items-center space-x-2">
            <ShieldAlert className="w-6 h-6 text-linear-primary" />
            <span>Activity & Risk Panel</span>
          </h2>
          <p className="text-linear-ink-muted text-sm mt-2 max-w-xl">
            Automatically flagged events from database triggers. Flags highlight potential compliance violations, off-hours access, or abnormal mutation rates.
          </p>
        </div>

        <div className="bg-linear-surface-1 border border-linear-hairline rounded-2xl p-6 flex items-center justify-between shadow-sm">
          <div>
            <p className="text-sm font-medium text-linear-ink-muted">Action Required</p>
            <div className="mt-2 flex items-baseline space-x-2">
              <span className={`text-4xl font-black tracking-tight font-mono ${unreviewedCount > 0 ? 'text-grafana-orange' : 'text-linear-success'}`}>
                {unreviewedCount}
              </span>
              <span className="text-sm text-linear-ink-subtle font-medium">unreviewed flags</span>
            </div>
          </div>
          <div className={`p-4 rounded-full ${unreviewedCount > 0 ? 'bg-grafana-orange/10' : 'bg-linear-success/10'}`}>
            <AlertTriangle className={`w-8 h-8 ${unreviewedCount > 0 ? 'text-grafana-orange' : 'text-linear-success'}`} />
          </div>
        </div>
      </div>

      {/* Main Panel */}
      <div className="bg-linear-surface-1 border border-linear-hairline rounded-2xl overflow-hidden shadow-sm">
        
        {/* Toolbar */}
        <div className="px-6 py-4 border-b border-linear-hairline flex flex-col sm:flex-row sm:items-center justify-between gap-4 bg-linear-surface-2/40">
          <h3 className="text-base font-semibold text-linear-ink">Flagged Events</h3>
          <div className="flex bg-linear-canvas p-1 rounded-xl border border-linear-hairline self-start sm:self-auto space-x-1" role="tablist" aria-label="Risk flag filter">
            <button
              type="button"
              role="tab"
              aria-selected={filter === 'unreviewed'}
              onClick={() => setFilter('unreviewed')}
              className={`px-3 py-1.5 text-xs font-semibold rounded-lg transition-colors duration-150 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-linear-primary ${
                filter === 'unreviewed' ? 'bg-linear-primary text-white shadow-xs' : 'text-linear-ink-muted hover:text-linear-ink'
              }`}
            >
              Unreviewed ({unreviewedCount})
            </button>
            <button
              type="button"
              role="tab"
              aria-selected={filter === 'all'}
              onClick={() => setFilter('all')}
              className={`px-3 py-1.5 text-xs font-semibold rounded-lg transition-colors duration-150 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-linear-primary ${
                filter === 'all' ? 'bg-linear-primary text-white shadow-xs' : 'text-linear-ink-muted hover:text-linear-ink'
              }`}
            >
              All Flags
            </button>
          </div>
        </div>

        {/* Flag List */}
        <div className="divide-y divide-linear-hairline/60 min-h-[400px]">
          {filteredFlags.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-24 text-linear-ink-subtle">
              <CheckCircle2 className="w-12 h-12 text-linear-success/40 mb-4" />
              <p className="text-sm font-medium text-linear-ink">No {filter === 'unreviewed' ? 'unreviewed' : ''} flags found.</p>
              <p className="text-xs mt-1 text-linear-ink-muted">The system is currently operating within normal parameters.</p>
            </div>
          ) : (
            filteredFlags.map((flag) => (
              <div key={flag.flag_id} className={`p-6 flex flex-col md:flex-row gap-6 transition-colors duration-150 ${flag.reviewed_at ? 'bg-linear-canvas/40 opacity-75' : 'hover:bg-linear-surface-2/60'}`}>
                
                {/* Left col: Status & Indicator */}
                <div className="flex-shrink-0 flex items-start space-x-4 md:w-48">
                  <div className="mt-1 flex-shrink-0">
                    {flag.reviewed_at ? (
                      <CheckCircle2 className="w-5 h-5 text-linear-success" />
                    ) : (
                      <AlertTriangle className="w-5 h-5 text-grafana-orange" />
                    )}
                  </div>
                  <div>
                    <span className="text-xs font-bold uppercase tracking-wider text-linear-ink-muted">Flag ID</span>
                    <p className="text-sm font-mono text-linear-ink mt-0.5">#{flag.flag_id}</p>
                    <p className="text-[11px] text-linear-ink-muted mt-2 font-mono">
                      {new Date(flag.created_at).toLocaleString()}
                    </p>
                  </div>
                </div>

                {/* Middle col: Reason & Context */}
                <div className="flex-grow min-w-0">
                  <div className="flex flex-col justify-center h-full">
                    <p className="text-sm text-linear-ink font-medium leading-relaxed">
                      {flag.flag_reason}
                    </p>
                    <div className="mt-3 flex items-center space-x-3 text-xs">
                      <span className="inline-flex items-center space-x-1.5 bg-linear-surface-2 px-2.5 py-1 rounded-md border border-linear-hairline text-linear-ink-muted text-xs">
                        <span className="text-linear-ink-subtle">Audit Seq:</span>
                        <span className="font-mono font-semibold text-linear-ink">#{flag.audit_log_sequence_id}</span>
                      </span>
                      {flag.reviewed_at && (
                        <span className="text-linear-success/80 flex items-center">
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
                      <Button
                        type="button"
                        size="sm"
                        variant="primary"
                        portalTheme="auditor"
                        loading={reviewMutation.isPending && reviewMutation.variables === flag.flag_id}
                        disabled={reviewMutation.isPending}
                        onClick={() => reviewMutation.mutate(flag.flag_id)}
                        leftIcon={<CheckCircle2 className="w-3.5 h-3.5" />}
                        className="w-full"
                      >
                        Mark Safe
                      </Button>
                      <div className="flex items-center gap-1.5">
                        <Link
                          to={`/auditor/chain?seq=${flag.audit_log_sequence_id}`}
                          className="btn-press-sm flex-1 flex items-center justify-center space-x-1 bg-linear-canvas hover:bg-linear-surface-2 text-linear-ink-muted hover:text-linear-ink text-[11px] py-1.5 px-2 rounded-md border border-linear-hairline transition-colors duration-150 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-linear-primary"
                          title="Inspect in Chain Explorer"
                        >
                          <GitCommit className="w-3 h-3 text-linear-primary" />
                          <span>Chain</span>
                        </Link>
                        <Link
                          to={`/auditor/log?seq=${flag.audit_log_sequence_id}`}
                          className="btn-press-sm flex-1 flex items-center justify-center space-x-1 bg-linear-canvas hover:bg-linear-surface-2 text-linear-ink-muted hover:text-linear-ink text-[11px] py-1.5 px-2 rounded-md border border-linear-hairline transition-colors duration-150 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-linear-primary"
                          title="View in Audit Log"
                        >
                          <span>Log</span>
                          <ArrowUpRight className="w-3 h-3 text-linear-ink-subtle" />
                        </Link>
                      </div>
                    </>
                  ) : (
                    <div className="flex items-center gap-1.5 w-full">
                      <Link
                        to={`/auditor/chain?seq=${flag.audit_log_sequence_id}`}
                        className="btn-press-sm flex-1 flex items-center justify-center space-x-1 bg-linear-canvas hover:bg-linear-surface-2 text-linear-ink-muted hover:text-linear-ink text-[11px] py-1.5 px-2 rounded-md border border-linear-hairline transition-colors duration-150 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-linear-primary"
                        title="Inspect in Chain Explorer"
                      >
                        <GitCommit className="w-3 h-3 text-linear-primary" />
                        <span>Chain</span>
                      </Link>
                      <Link
                        to={`/auditor/log?seq=${flag.audit_log_sequence_id}`}
                        className="btn-press-sm flex-1 flex items-center justify-center space-x-1 bg-linear-canvas hover:bg-linear-surface-2 text-linear-ink-muted hover:text-linear-ink text-[11px] py-1.5 px-2 rounded-md border border-linear-hairline transition-colors duration-150 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-linear-primary"
                        title="View in Audit Log"
                      >
                        <span>View Log</span>
                        <ArrowUpRight className="w-3 h-3 text-linear-ink-subtle" />
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
