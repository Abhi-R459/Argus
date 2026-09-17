import { useQuery } from '@tanstack/react-query';
import { useAuth } from '@clerk/clerk-react';
import { Users, ShieldCheck, AlertTriangle, Clock, Activity } from 'lucide-react';
import { fetchDashboardStats, type DashboardStats } from '../../services/auditService';
import RefreshButton from '../../components/common/RefreshButton';

function formatRelativeTime(isoString: string): string {
  try {
    const diff = Math.max(0, Date.now() - new Date(isoString).getTime());
    const seconds = Math.floor(diff / 1000);
    if (seconds < 5) return 'just now';
    if (seconds < 60) return `${seconds}s ago`;
    const minutes = Math.floor(seconds / 60);
    if (minutes < 60) return `${minutes}m ago`;
    const hours = Math.floor(minutes / 60);
    if (hours < 24) return `${hours}h ago`;
    const days = Math.floor(hours / 24);
    return `${days}d ago`;
  } catch {
    return isoString;
  }
}

const ACTION_COLORS: Record<string, string> = {
  INSERT: 'bg-emerald-50 text-emerald-700 border-emerald-200/80',
  UPDATE: 'bg-amber-50 text-amber-700 border-amber-200/80',
  DELETE: 'bg-rose-50 text-rose-700 border-rose-200/80',
};

export default function Dashboard() {
  const { getToken } = useAuth();

  const { data, isLoading, isError, refetch } = useQuery<DashboardStats>({
    queryKey: ['dashboardStats'],
    queryFn: () => fetchDashboardStats(() => getToken()),
    refetchInterval: 3000,
  });

  return (
    <div className="space-y-8 animate-fade-cascade">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-slate-900 tracking-tight">HR Operations Overview</h1>
          <p className="text-slate-500 text-sm mt-1">
            Real-time workforce metrics and tamper-evident audit status directly from PostgreSQL.
          </p>
        </div>
        <RefreshButton
          onRefresh={() => refetch()}
          label="Refresh Stats"
          variant="light"
          title="Refresh workforce metrics"
        />
      </div>

      {/* Metrics Row - Stripe/Linear Style Tactile Cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        {/* Total Active Employees */}
        <div className="card-hover bg-white rounded-2xl shadow-[0_1px_3px_rgba(0,0,0,0.04),0_1px_2px_rgba(0,0,0,0.02)] border border-slate-200/90 p-6 flex flex-col justify-between relative overflow-hidden">
          <div className="absolute top-0 left-0 right-0 h-1 bg-gradient-to-r from-indigo-500 via-indigo-600 to-indigo-400" />
          <div className="flex items-center justify-between">
            <span className="text-[11px] font-bold uppercase tracking-wider text-slate-400 font-mono">Active Workforce</span>
            <div className="p-2.5 bg-indigo-50 text-indigo-600 rounded-xl border border-indigo-100">
              <Users className="w-5 h-5" />
            </div>
          </div>
          <div className="mt-5">
            {isLoading ? (
              <div className="h-10 w-24 bg-slate-100 animate-pulse rounded-lg" />
            ) : (
              <p className="text-3xl font-extrabold text-slate-900 tracking-tight font-sans tabular-nums">
                {data?.active_employees ?? 0}
              </p>
            )}
            <div className="mt-3 flex items-center justify-between pt-3 border-t border-slate-100 text-xs">
              <span className="text-slate-500">Total Registered</span>
              <span className="font-semibold text-slate-800 font-mono bg-slate-100 px-2 py-0.5 rounded-md">
                {data?.total_employees ?? 0} profiles
              </span>
            </div>
          </div>
        </div>

        {/* Total Audit Events */}
        <div className="card-hover bg-white rounded-2xl shadow-[0_1px_3px_rgba(0,0,0,0.04),0_1px_2px_rgba(0,0,0,0.02)] border border-slate-200/90 p-6 flex flex-col justify-between relative overflow-hidden">
          <div className="absolute top-0 left-0 right-0 h-1 bg-gradient-to-r from-emerald-500 via-teal-500 to-emerald-400" />
          <div className="flex items-center justify-between">
            <span className="text-[11px] font-bold uppercase tracking-wider text-slate-400 font-mono">Audit Trail Events</span>
            <div className="p-2.5 bg-emerald-50 text-emerald-600 rounded-xl border border-emerald-100">
              <ShieldCheck className="w-5 h-5" />
            </div>
          </div>
          <div className="mt-5">
            {isLoading ? (
              <div className="h-10 w-24 bg-slate-100 animate-pulse rounded-lg" />
            ) : (
              <p className="text-3xl font-extrabold text-slate-900 tracking-tight font-sans tabular-nums">
                {data?.total_audit_events ?? 0}
              </p>
            )}
            <div className="mt-3 flex items-center justify-between pt-3 border-t border-slate-100 text-xs">
              <span className="text-emerald-700 font-medium flex items-center">
                <span className="inline-block w-2 h-2 rounded-full bg-emerald-500 mr-1.5 animate-pulse" />
                Chained & Sealed
              </span>
              <span className="font-semibold text-emerald-800 font-mono bg-emerald-50 px-2 py-0.5 rounded-md border border-emerald-200/60">
                100% Intact
              </span>
            </div>
          </div>
        </div>

        {/* Suspicious Flags */}
        <div className="card-hover bg-white rounded-2xl shadow-[0_1px_3px_rgba(0,0,0,0.04),0_1px_2px_rgba(0,0,0,0.02)] border border-slate-200/90 p-6 flex flex-col justify-between relative overflow-hidden">
          <div className="absolute top-0 left-0 right-0 h-1 bg-gradient-to-r from-amber-500 via-orange-500 to-amber-400" />
          <div className="flex items-center justify-between">
            <span className="text-[11px] font-bold uppercase tracking-wider text-slate-400 font-mono">Compliance Flags</span>
            <div className={`p-2.5 rounded-xl border ${
              (data?.unreviewed_flags ?? 0) > 0
                ? 'bg-amber-50 text-amber-600 border-amber-200'
                : 'bg-slate-50 text-slate-500 border-slate-200'
            }`}>
              <AlertTriangle className="w-5 h-5" />
            </div>
          </div>
          <div className="mt-5">
            {isLoading ? (
              <div className="h-10 w-24 bg-slate-100 animate-pulse rounded-lg" />
            ) : (
              <p className="text-3xl font-extrabold text-slate-900 tracking-tight font-sans tabular-nums">
                {data?.unreviewed_flags ?? 0}
              </p>
            )}
            <div className="mt-3 flex items-center justify-between pt-3 border-t border-slate-100 text-xs">
              <span className="text-slate-500">Trigger Status</span>
              <span className={`font-semibold font-mono px-2 py-0.5 rounded-md ${
                (data?.unreviewed_flags ?? 0) > 0
                  ? 'bg-amber-50 text-amber-800 border border-amber-200'
                  : 'bg-slate-100 text-slate-600'
              }`}>
                {(data?.unreviewed_flags ?? 0) > 0 ? 'Requires Review' : '0 Anomalies'}
              </span>
            </div>
          </div>
        </div>
      </div>

      {/* Live Recent Activity */}
      <div className="bg-white rounded-2xl shadow-[0_1px_3px_rgba(0,0,0,0.04),0_1px_2px_rgba(0,0,0,0.02)] border border-slate-200/90 p-6">
        <div className="flex items-center justify-between mb-6 pb-4 border-b border-slate-100">
          <div className="flex items-center space-x-3">
            <div className="p-2 rounded-xl bg-indigo-50 text-indigo-600 border border-indigo-100">
              <Activity className="w-5 h-5" />
            </div>
            <div>
              <h2 className="text-base font-bold text-slate-900 tracking-tight">Live Mutation Stream</h2>
              <p className="text-xs text-slate-500">Real-time audit records emitted by PostgreSQL triggers</p>
            </div>
          </div>
          <span className="text-xs font-mono text-slate-500 bg-slate-50 px-2.5 py-1 rounded-lg border border-slate-200/70 flex items-center space-x-1.5">
            <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
            <span>table: audit_log</span>
          </span>
        </div>

        {isLoading ? (
          <div className="space-y-3 py-4">
            {[1, 2, 3, 4].map((i) => (
              <div key={i} className="h-12 bg-slate-50 animate-pulse rounded-xl border border-slate-100" />
            ))}
          </div>
        ) : isError ? (
          <div className="flex flex-col items-center justify-center py-12 text-slate-400">
            <AlertTriangle className="w-8 h-8 text-amber-500 mb-2" />
            <p className="text-sm font-medium">Unable to load live activity stream.</p>
          </div>
        ) : (!data?.recent_activity || data.recent_activity.length === 0) ? (
          <div className="flex flex-col items-center justify-center py-12 text-slate-400 bg-slate-50/50 rounded-xl border border-dashed border-slate-200">
            <Clock className="w-10 h-10 text-slate-300 mb-2" />
            <p className="text-sm font-medium">No audit mutations logged yet.</p>
          </div>
        ) : (
          <div className="divide-y divide-slate-100">
            {data.recent_activity.map((activity, idx) => (
              <div
                key={activity.sequence_id}
                style={{ animationDelay: `${idx * 35}ms` }}
                className="animate-fade-cascade py-3.5 px-3 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 hover:bg-slate-50/90 rounded-xl transition-colors duration-150 group"
              >
                <div className="flex items-center space-x-3.5">
                  <span className="font-mono text-xs font-bold text-slate-500 bg-slate-100/90 px-2 py-1 rounded-md border border-slate-200/70">
                    #{activity.sequence_id.toString().padStart(4, '0')}
                  </span>
                  <span
                    className={`text-[11px] font-bold uppercase tracking-wider px-2.5 py-0.5 rounded-full border shadow-2xs ${
                      ACTION_COLORS[activity.action] || 'bg-slate-100 text-slate-700 border-slate-200'
                    }`}
                  >
                    {activity.action}
                  </span>
                  <div className="text-sm">
                    <span className="font-bold text-slate-900">{activity.actor_name}</span>
                    <span className="text-slate-400 mx-1.5 text-xs">modified</span>
                    <code className="text-xs font-mono font-semibold text-indigo-700 bg-indigo-50/80 px-2 py-0.5 rounded-md border border-indigo-100">
                      {activity.table_name}
                    </code>
                  </div>
                </div>

                <div className="text-xs font-medium text-slate-400 flex items-center pl-16 sm:pl-0 font-mono">
                  <Clock className="w-3.5 h-3.5 mr-1.5 text-slate-400" />
                  {formatRelativeTime(activity.created_at)}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

