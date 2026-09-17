import { useQuery } from '@tanstack/react-query';
import { useAuth } from '@clerk/clerk-react';
import { Database, Zap, HardDrive, Table, Loader2 } from 'lucide-react';
import { fetchSystemMetrics, type SystemMetrics } from '../../services/auditService';
import RefreshButton from '../common/RefreshButton';

export default function QueryPanel() {
  const { getToken } = useAuth();

  const { data, isLoading, isError, refetch } = useQuery<SystemMetrics>({
    queryKey: ['systemMetrics'],
    queryFn: () => fetchSystemMetrics(() => getToken()),
    refetchInterval: 4000,
  });

  return (
    <div className="bg-[#0F172A]/80 border border-slate-800/80 rounded-2xl overflow-hidden shadow-sm animate-fade-cascade">
      <div className="px-6 py-5 border-b border-slate-800/80 bg-[#0B0F17]/50 flex items-center justify-between">
        <div className="flex items-center space-x-3">
          <div className="p-2 bg-sky-500/10 rounded-lg border border-sky-500/20">
            <Database className="w-5 h-5 text-sky-400" />
          </div>
          <div>
            <h3 className="text-base font-semibold text-slate-100">Database Engine Telemetry</h3>
            <p className="text-xs text-slate-400 mt-0.5">Live metrics from pg_stat_database & pg_stat_user_tables</p>
          </div>
        </div>
        <div className="flex items-center space-x-3">
          <RefreshButton
            onRefresh={() => refetch()}
            variant="icon-dark"
            title="Refresh metrics"
          />
          <span className="inline-flex items-center space-x-1.5 px-2.5 py-1 bg-emerald-500/10 text-emerald-400 text-xs font-medium rounded-md border border-emerald-500/20">
            <div className="w-1.5 h-1.5 bg-emerald-400 rounded-full animate-pulse" />
            <span>PostgreSQL Active</span>
          </span>
        </div>
      </div>

      {/* High-level metrics */}
      <div className="grid grid-cols-3 divide-x divide-slate-800/80 border-b border-slate-800/80">
        <div className="p-5 flex flex-col items-center text-center">
          <Zap className="w-5 h-5 text-amber-400 mb-2 opacity-80" />
          {isLoading ? (
            <Loader2 className="w-6 h-6 text-slate-400 animate-fast-spin" />
          ) : (
            <span className="text-2xl font-bold font-mono text-slate-100">{data?.cache_hit_rate ?? 0}%</span>
          )}
          <span className="text-xs text-slate-400 uppercase font-semibold mt-1">Buffer Cache Hit</span>
        </div>
        <div className="p-5 flex flex-col items-center text-center">
          <HardDrive className="w-5 h-5 text-sky-400 mb-2 opacity-80" />
          {isLoading ? (
            <Loader2 className="w-6 h-6 text-slate-400 animate-fast-spin" />
          ) : (
            <span className="text-2xl font-bold font-mono text-slate-100">{data?.db_size ?? 'N/A'}</span>
          )}
          <span className="text-xs text-slate-400 uppercase font-semibold mt-1">Database Size</span>
        </div>
        <div className="p-5 flex flex-col items-center text-center">
          <Table className="w-5 h-5 text-violet-400 mb-2 opacity-80" />
          {isLoading ? (
            <Loader2 className="w-6 h-6 text-slate-400 animate-fast-spin" />
          ) : (
            <span className="text-2xl font-bold font-mono text-slate-100">{data?.audit_log_size ?? 'N/A'}</span>
          )}
          <span className="text-xs text-slate-400 uppercase font-semibold mt-1">Audit Log Relation</span>
        </div>
      </div>

      {/* Table Stats */}
      <div className="overflow-x-auto">
        <table className="w-full text-sm text-left">
          <thead className="bg-[#0B0F17]/80 text-xs text-slate-400 uppercase tracking-wider border-b border-slate-800/80">
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
                <td colSpan={5} className="px-6 py-8 text-center text-slate-400">
                  <Loader2 className="w-5 h-5 text-slate-400 animate-fast-spin inline mr-2" />
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
