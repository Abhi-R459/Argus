import { useQuery } from '@tanstack/react-query';
import { useAuth } from '@clerk/clerk-react';
import { Users, ShieldCheck, AlertTriangle, Clock, RefreshCw, Activity } from 'lucide-react';
import { fetchDashboardStats, type DashboardStats } from '../../services/auditService';

function formatRelativeTime(isoString: string): string {
  try {
    const diff = Date.now() - new Date(isoString).getTime();
    const minutes = Math.floor(diff / 60000);
    if (minutes < 1) return 'just now';
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
  INSERT: 'bg-emerald-50 text-emerald-700 border-emerald-200',
  UPDATE: 'bg-amber-50 text-amber-700 border-amber-200',
  DELETE: 'bg-rose-50 text-rose-700 border-rose-200',
};

export default function Dashboard() {
  const { getToken } = useAuth();

  const { data, isLoading, isError, refetch } = useQuery<DashboardStats>({
    queryKey: ['dashboardStats'],
    queryFn: () => fetchDashboardStats(() => getToken()),
    refetchInterval: 10000,
  });

  return (
    <div className="animate-in fade-in slide-in-from-bottom-4 duration-500 space-y-8">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-slate-900 tracking-tight">HR Operations Overview</h1>
          <p className="text-slate-500 text-sm mt-1">
            Real-time workforce metrics and tamper-evident audit status directly from PostgreSQL.
          </p>
        </div>
        <button
          onClick={() => refetch()}
          className="inline-flex items-center px-3.5 py-2 rounded-lg border border-slate-200 bg-white hover:bg-slate-50 text-slate-700 text-xs font-semibold shadow-sm transition-colors"
        >
          <RefreshCw className="w-3.5 h-3.5 mr-1.5 text-slate-500" />
          Refresh Stats
        </button>
      </div>

      {/* Metrics Row */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        {/* Total Active Employees */}
        <div className="bg-white rounded-xl shadow-sm border border-slate-200/80 p-6 flex flex-col justify-between hover:shadow-md transition-all">
          <div className="flex items-center justify-between">
            <h3 className="text-sm font-semibold text-slate-500">Active Workforce</h3>
            <div className="p-2.5 bg-indigo-50 text-indigo-600 rounded-lg">
              <Users className="w-5 h-5" />
            </div>
          </div>
          <div className="mt-4">
            {isLoading ? (
              <div className="h-9 w-24 bg-slate-100 animate-pulse rounded" />
            ) : (
              <p className="text-3xl font-extrabold text-slate-900 tracking-tight">
                {data?.active_employees ?? 0}
              </p>
            )}
            <p className="text-xs text-slate-500 mt-2 flex items-center">
              <span className="font-medium text-slate-700 mr-1">{data?.total_employees ?? 0}</span>
              total profiles registered in database
            </p>
          </div>
        </div>

        {/* Total Audit Events */}
        <div className="bg-white rounded-xl shadow-sm border border-slate-200/80 p-6 flex flex-col justify-between hover:shadow-md transition-all">
          <div className="flex items-center justify-between">
            <h3 className="text-sm font-semibold text-slate-500">Audit Trail Events</h3>
            <div className="p-2.5 bg-emerald-50 text-emerald-600 rounded-lg">
              <ShieldCheck className="w-5 h-5" />
            </div>
          </div>
          <div className="mt-4">
            {isLoading ? (
              <div className="h-9 w-24 bg-slate-100 animate-pulse rounded" />
            ) : (
              <p className="text-3xl font-extrabold text-slate-900 tracking-tight">
                {data?.total_audit_events ?? 0}
              </p>
            )}
            <p className="text-xs text-emerald-600 font-medium mt-2 flex items-center">
              <span className="inline-block w-2 h-2 rounded-full bg-emerald-500 mr-1.5 animate-pulse" />
              Cryptographically chained & sealed
            </p>
          </div>
        </div>

        {/* Suspicious Flags */}
        <div className="bg-white rounded-xl shadow-sm border border-slate-200/80 p-6 flex flex-col justify-between hover:shadow-md transition-all">
          <div className="flex items-center justify-between">
            <h3 className="text-sm font-semibold text-slate-500">Compliance Flags</h3>
            <div className={`p-2.5 rounded-lg ${
              (data?.unreviewed_flags ?? 0) > 0 ? 'bg-amber-50 text-amber-600' : 'bg-slate-50 text-slate-600'
            }`}>
              <AlertTriangle className="w-5 h-5" />
            </div>
          </div>
          <div className="mt-4">
            {isLoading ? (
              <div className="h-9 w-24 bg-slate-100 animate-pulse rounded" />
            ) : (
              <p className="text-3xl font-extrabold text-slate-900 tracking-tight">
                {data?.unreviewed_flags ?? 0}
              </p>
            )}
            <p className="text-xs text-slate-500 mt-2">
              {(data?.unreviewed_flags ?? 0) > 0
                ? 'Unreviewed triggers require attention'
                : 'Zero unreviewed security flags'}
            </p>
          </div>
        </div>
      </div>

      {/* Live Recent Activity */}
      <div className="bg-white rounded-xl shadow-sm border border-slate-200/80 p-6">
        <div className="flex items-center justify-between mb-6">
          <div className="flex items-center space-x-2.5">
            <Activity className="w-5 h-5 text-indigo-600" />
            <h2 className="text-lg font-semibold text-slate-900">Recent Database Activity</h2>
          </div>
          <span className="text-xs font-medium text-slate-500">
            Live Stream from <code className="text-slate-700 bg-slate-100 px-1.5 py-0.5 rounded font-mono">audit_log</code>
          </span>
        </div>

        {isLoading ? (
          <div className="space-y-3 py-6">
            {[1, 2, 3, 4].map((i) => (
              <div key={i} className="h-12 bg-slate-50 animate-pulse rounded-lg" />
            ))}
          </div>
        ) : isError ? (
          <div className="flex flex-col items-center justify-center py-12 text-slate-400">
            <AlertTriangle className="w-8 h-8 text-amber-500 mb-2" />
            <p className="text-sm">Unable to load live activity stream.</p>
          </div>
        ) : (!data?.recent_activity || data.recent_activity.length === 0) ? (
          <div className="flex flex-col items-center justify-center py-12 text-slate-400 bg-slate-50/50 rounded-lg border border-dashed border-slate-200">
            <Clock className="w-10 h-10 text-slate-300 mb-2" />
            <p className="text-sm">No audit mutations logged yet.</p>
          </div>
        ) : (
          <div className="divide-y divide-slate-100">
            {data.recent_activity.map((activity) => (
              <div
                key={activity.sequence_id}
                className="py-3.5 px-2 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 hover:bg-slate-50/80 rounded-lg transition-colors"
              >
                <div className="flex items-center space-x-3.5">
                  <span className="text-xs font-mono font-semibold text-slate-400 w-12">
                    #{activity.sequence_id}
                  </span>
                  <span
                    className={`text-[11px] font-bold uppercase tracking-wider px-2 py-0.5 rounded border ${
                      ACTION_COLORS[activity.action] || 'bg-slate-100 text-slate-700 border-slate-200'
                    }`}
                  >
                    {activity.action}
                  </span>
                  <div className="text-sm">
                    <span className="font-medium text-slate-800">{activity.actor_name}</span>
                    <span className="text-slate-400 mx-1.5">modified</span>
                    <code className="text-xs font-mono text-slate-700 bg-slate-100 px-1.5 py-0.5 rounded">
                      {activity.table_name}
                    </code>
                  </div>
                </div>

                <div className="text-xs text-slate-400 flex items-center pl-15 sm:pl-0">
                  <Clock className="w-3.5 h-3.5 mr-1 text-slate-400" />
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
