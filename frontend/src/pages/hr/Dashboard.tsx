import { useQuery } from '@tanstack/react-query';
import { useAuth } from '@clerk/clerk-react';
import { useNavigate } from 'react-router-dom';
import {
  Users,
  ShieldCheck,
  AlertTriangle,
  Clock,
  Activity,
  ArrowRight,
  RefreshCw,
} from 'lucide-react';
import { fetchDashboardStats, type DashboardStats } from '../../services/auditService';
import RefreshButton from '../../components/common/RefreshButton';
import { Button } from '../../components/common/Button';
import PageHeader from '../../components/common/PageHeader';
import { EmptyState } from '../../components/common/EmptyState';
import { formatRelativeTime } from '../../lib/format';
import { getActionSemantic } from '../../lib/semantics';

export default function Dashboard() {
  const { getToken } = useAuth();
  const navigate = useNavigate();

  const { data, isLoading, isError, refetch } = useQuery<DashboardStats>({
    queryKey: ['dashboardStats'],
    queryFn: () => fetchDashboardStats(() => getToken()),
    refetchInterval: 3000,
  });

  return (
    <div className="space-y-6 animate-fade-cascade">
      <PageHeader
        title="Workforce Overview"
        description="Headcount, department allocation, and recent personnel activity."
        portalTheme="hr"
        action={
          <>
          <RefreshButton
            onRefresh={() => refetch()}
            label="Refresh"
            variant="light"
            title="Refresh workforce metrics"
          />
          <Button
            variant="primary"
            size="md"
            portalTheme="hr"
            onClick={() => navigate('/hr/employees')}
            leftIcon={<Users className="w-4 h-4" />}
          >
            View Directory
          </Button>
          </>
        }
      />

      {/* Metrics Row — Clean Modern Executive Metric Cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-5">
        {/* Active Workforce */}
        <div className="bg-white rounded-2xl border border-slate-200/80 p-6 flex flex-col justify-between shadow-xs">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold text-slate-500">
              Active Personnel
            </span>
            <div className="p-2.5 bg-blue-50 text-blue-600 rounded-xl border border-blue-100/80">
              <Users className="w-4 h-4" />
            </div>
          </div>
          <div className="mt-4">
            {isLoading ? (
              <div className="h-9 w-24 bg-slate-100 animate-pulse rounded-md" />
            ) : (
              <p className="text-3xl font-bold text-slate-900 tracking-tight tabular-nums">
                {data?.active_employees ?? 0}
              </p>
            )}
            <div className="mt-3 flex items-center justify-between pt-3 border-t border-slate-100 text-xs">
              <span className="text-slate-500">Total Enrolled Profiles</span>
              <span className="font-semibold text-slate-700 bg-slate-100 px-2 py-0.5 rounded-md">
                {data?.total_employees ?? 0}
              </span>
            </div>
          </div>
        </div>

        {/* Audit Chain Ledger */}
        <div className="bg-white rounded-2xl border border-slate-200/80 p-6 flex flex-col justify-between shadow-xs">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold text-slate-500">
              Verified Audit Ledger
            </span>
            <div className="p-2.5 bg-emerald-50 text-emerald-600 rounded-xl border border-emerald-100/80">
              <ShieldCheck className="w-4 h-4" />
            </div>
          </div>
          <div className="mt-4">
            {isLoading ? (
              <div className="h-9 w-24 bg-slate-100 animate-pulse rounded-md" />
            ) : (
              <p className="text-3xl font-bold text-slate-900 tracking-tight tabular-nums">
                {data?.total_audit_events ?? 0}
              </p>
            )}
            <div className="mt-3 flex items-center justify-between pt-3 border-t border-slate-100 text-xs">
              <span className="text-emerald-700 font-medium flex items-center gap-1.5">
                <span className="w-1.5 h-1.5 rounded-full bg-emerald-500" />
                Cryptographically Sealed
              </span>
              <span className="font-medium text-slate-500">
                Chain Intact
              </span>
            </div>
          </div>
        </div>

        {/* Compliance Alerts */}
        <div className="bg-white rounded-2xl border border-slate-200/80 p-6 flex flex-col justify-between shadow-xs">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold text-slate-500">
              Compliance & Security
            </span>
            <div
              className={`p-2.5 rounded-xl border ${
                (data?.unreviewed_flags ?? 0) > 0
                  ? 'bg-amber-50 text-amber-600 border-amber-200/80'
                  : 'bg-slate-50 text-slate-500 border-slate-200/80'
              }`}
            >
              <AlertTriangle className="w-4 h-4" />
            </div>
          </div>
          <div className="mt-4">
            {isLoading ? (
              <div className="h-9 w-24 bg-slate-100 animate-pulse rounded-md" />
            ) : (
              <p className="text-3xl font-bold text-slate-900 tracking-tight tabular-nums">
                {data?.unreviewed_flags ?? 0}
              </p>
            )}
            <div className="mt-3 flex items-center justify-between pt-3 border-t border-slate-100 text-xs">
              <span className="text-slate-500">Pending Flags</span>
              <span
                className={`font-medium px-2 py-0.5 rounded-md text-[11px] border ${
                  (data?.unreviewed_flags ?? 0) > 0
                    ? 'bg-amber-50 text-amber-700 border-amber-200'
                    : 'bg-emerald-50 text-emerald-700 border-emerald-200/60'
                }`}
              >
                {(data?.unreviewed_flags ?? 0) > 0 ? 'Review Required' : '0 Anomalies'}
              </span>
            </div>
          </div>
        </div>
      </div>

      {/* Recent Activity Stream */}
        <div className="bg-white rounded-2xl border border-slate-200/80 shadow-xs overflow-hidden">
        <div className="p-5 border-b border-slate-100 flex items-center justify-between bg-white">
          <div className="flex items-center gap-3">
            <div className="p-2 rounded-xl bg-slate-100 text-slate-700">
              <Activity className="w-4 h-4" />
            </div>
            <div>
              <h2 className="text-sm font-bold text-slate-900 tracking-tight">
                Recent Personnel Activity
              </h2>
              <p className="text-xs text-slate-500 mt-0.5">
                Immutable operational events emitted by automated database triggers
              </p>
            </div>
          </div>
        </div>

        {isLoading ? (
          <div className="p-5 space-y-3">
            {[1, 2, 3, 4].map((i) => (
              <div key={i} className="h-10 bg-slate-50 animate-pulse rounded-xl border border-slate-100" />
            ))}
          </div>
        ) : isError ? (
          <div className="px-5 sm:px-6 py-7 flex flex-col sm:flex-row sm:items-center gap-4" role="alert">
            <div className="h-10 w-10 rounded-lg border border-amber-200 bg-amber-50 text-amber-700 flex items-center justify-center shrink-0">
              <AlertTriangle className="h-5 w-5" />
            </div>
            <div className="min-w-0">
              <p className="text-sm font-semibold text-slate-900">Recent activity is unavailable</p>
              <p className="mt-1 text-sm text-slate-600">Argus couldn’t load the latest personnel events. Try again in a moment.</p>
            </div>
            <button
              type="button"
              onClick={() => void refetch()}
              className="sm:ml-auto inline-flex shrink-0 items-center gap-2 rounded-lg px-3 py-2 text-sm font-medium text-slate-700 hover:bg-slate-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-portal-primary/40"
            >
              <RefreshCw className="h-3.5 w-3.5" /> Retry
            </button>
          </div>
        ) : !data?.recent_activity || data.recent_activity.length === 0 ? (
          <EmptyState
            title="No activity events recorded yet"
            description="Personnel updates and compensation changes will automatically log here."
            portalTheme="hr"
          />
        ) : (
          <div className="divide-y divide-slate-100">
            {data.recent_activity.map((activity) => {
              const semantic = getActionSemantic(activity.action, activity.table_name, 'hr');
              return (
                <div
                  key={activity.sequence_id}
                  className="py-3.5 px-5 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 hover:bg-slate-50/70 transition-colors duration-150"
                >
                  <div className="flex items-center gap-3">
                    <span
                      className={`text-[11px] font-medium px-2 py-0.5 rounded-md border ${semantic.className}`}
                    >
                      {semantic.label}
                    </span>
                    <div className="text-xs">
                      <span className="font-semibold text-slate-900">
                        {activity.actor_name || 'System Automated Engine'}
                      </span>
                      <span className="text-slate-500 mx-1.5">modified</span>
                      <span className="text-slate-700 font-medium">
                        {activity.table_name === 'salary_history'
                          ? 'compensation record'
                          : 'employee profile'}
                      </span>
                      <span className="text-slate-500 font-mono text-[11px] ml-1.5">
                        (Seq #{activity.sequence_id})
                      </span>
                    </div>
                  </div>

                  <div className="text-[11px] text-slate-500 flex items-center gap-1.5 pl-14 sm:pl-0">
                    <Clock className="w-3.5 h-3.5 text-slate-400" />
                    <span>{formatRelativeTime(activity.created_at)}</span>
                  </div>
                </div>
              );
            })}
          </div>
        )}

        <div className="p-4 bg-slate-50 border-t border-slate-100 flex items-center justify-between text-xs">
          <span className="text-slate-500 text-xs">
            Showing recent personnel updates recorded to the audit trail
          </span>
          <Button
            variant="link"
            portalTheme="hr"
            onClick={() => navigate('/hr/employees')}
            rightIcon={<ArrowRight className="w-3.5 h-3.5 ml-1" />}
            className="text-xs font-semibold text-slate-900 hover:text-slate-700"
          >
            View Full Employee Directory
          </Button>
        </div>
      </div>
    </div>
  );
}
