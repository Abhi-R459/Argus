import { useQuery } from '@tanstack/react-query';
import { useAuth } from '@clerk/clerk-react';
import { Database, Zap, HardDrive, Table, RefreshCw, Loader2 } from 'lucide-react';
import { fetchSystemMetrics, type SystemMetrics } from '../../services/auditService';

export default function QueryPanel() {
  const { getToken } = useAuth();

  const { data, isLoading, isError, refetch } = useQuery<SystemMetrics>({
    queryKey: ['systemMetrics'],
    queryFn: () => fetchSystemMetrics(() => getToken()),
    refetchInterval: 10000,
  });

  return (
    <div className="bg-slate-900/50 border border-slate-700/50 rounded-2xl overflow-hidden shadow-xl shadow-black/20 animate-in fade-in slide-in-from-bottom-4 duration-500 delay-100">
      <div className="px-6 py-5 border-b border-slate-700/50 bg-slate-900/80 flex items-center justify-between">
        <div className="flex items-center space-x-3">
          <div className="p-2 bg-blue-500/10 rounded-lg">
            <Database className="w-5 h-5 text-blue-400" />
          </div>
          <div>
            <h3 className="text-base font-semibold text-slate-200">Database Engine Telemetry</h3>
            <p className="text-xs text-slate-400 mt-0.5">Live metrics from pg_stat_database & pg_stat_user_tables</p>
          </div>
        </div>
        <div className="flex items-center space-x-3">
          <button
            onClick={() => refetch()}
            className="text-slate-400 hover:text-slate-200 p-1.5 rounded-lg hover:bg-slate-800 transition-colors"
            title="Refresh metrics"
          >
            <RefreshCw className="w-3.5 h-3.5" />
          </button>
          <span className="inline-flex items-center space-x-1 px-2.5 py-1 bg-emerald-500/10 text-emerald-400 text-xs font-medium rounded border border-emerald-500/20">
            <div className="w-1.5 h-1.5 bg-emerald-400 rounded-full animate-pulse" />
            <span>PostgreSQL Active</span>
          </span>
        </div>
      </div>

      {/* High-level metrics */}
      <div className="grid grid-cols-3 divide-x divide-slate-800 border-b border-slate-800">
        <div className="p-5 flex flex-col items-center text-center">
          <Zap className="w-5 h-5 text-amber-400 mb-2 opacity-80" />
          {isLoading ? (
            <Loader2 className="w-6 h-6 text-slate-500 animate-spin" />
          ) : (
            <span className="text-2xl font-bold text-slate-200">{data?.cache_hit_rate ?? 0}%</span>
          )}
          <span className="text-xs text-slate-500 uppercase font-semibold mt-1">Buffer Cache Hit</span>
        </div>
        <div className="p-5 flex flex-col items-center text-center">
          <HardDrive className="w-5 h-5 text-blue-400 mb-2 opacity-80" />
          {isLoading ? (
            <Loader2 className="w-6 h-6 text-slate-500 animate-spin" />
          ) : (
            <span className="text-2xl font-bold text-slate-200">{data?.db_size ?? 'N/A'}</span>
          )}
          <span className="text-xs text-slate-500 uppercase font-semibold mt-1">Database Size</span>
        </div>
        <div className="p-5 flex flex-col items-center text-center">
          <Table className="w-5 h-5 text-violet-400 mb-2 opacity-80" />
          {isLoading ? (
            <Loader2 className="w-6 h-6 text-slate-500 animate-spin" />
          ) : (
            <span className="text-2xl font-bold text-slate-200">{data?.audit_log_size ?? 'N/A'}</span>
          )}
          <span className="text-xs text-slate-500 uppercase font-semibold mt-1">Audit Log Relation</span>
        </div>
      </div>

      {/* Table Stats */}
      <div className="overflow-x-auto">
        <table className="w-full text-sm text-left">
          <thead className="bg-slate-900/40 text-xs text-slate-500 uppercase tracking-wider border-b border-slate-800">
            <tr>
              <th className="px-6 py-3 font-medium">Table Name</th>
              <th className="px-6 py-3 font-medium">Seq Scans</th>
              <th className="px-6 py-3 font-medium">Index Scans</th>
              <th className="px-6 py-3 font-medium">Inserts (Tuples)</th>
              <th className="px-6 py-3 font-medium">Updates (Tuples)</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-800/60">
            {isLoading ? (
              <tr>
                <td colSpan={5} className="px-6 py-8 text-center text-slate-500">
                  <Loader2 className="w-5 h-5 text-slate-400 animate-spin inline mr-2" />
                  Reading pg_stat_user_tables...
                </td>
              </tr>
            ) : isError || !data?.table_stats || data.table_stats.length === 0 ? (
              <tr>
                <td colSpan={5} className="px-6 py-8 text-center text-slate-500">
                  No table statistics available.
                </td>
              </tr>
            ) : (
              data.table_stats.map((stat) => (
                <tr key={stat.table_name} className="hover:bg-slate-800/30 transition-colors group">
                  <td className="px-6 py-3.5 font-mono text-xs text-slate-300">
                    <code className="text-violet-300 bg-violet-500/10 px-1.5 py-0.5 rounded">
                      {stat.table_name}
                    </code>
                  </td>
                  <td className="px-6 py-3.5 text-slate-400 font-mono text-xs">
                    {stat.seq_scans.toLocaleString()}
                  </td>
                  <td className="px-6 py-3.5 text-slate-300 font-mono text-xs">
                    <span className="text-emerald-400">{stat.idx_scans.toLocaleString()}</span>
                  </td>
                  <td className="px-6 py-3.5 text-slate-300 font-mono text-xs">
                    {stat.inserts.toLocaleString()}
                  </td>
                  <td className="px-6 py-3.5 text-slate-300 font-mono text-xs">
                    {stat.updates.toLocaleString()}
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      <div className="px-6 py-3 bg-slate-900/60 border-t border-slate-800 text-xs text-slate-500 flex items-center justify-between">
        <span>Source: PostgreSQL pg_stat_user_tables</span>
        <span>Real-time engine telemetry</span>
      </div>
    </div>
  );
}
