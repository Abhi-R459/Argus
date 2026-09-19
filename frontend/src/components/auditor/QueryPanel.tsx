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
    <div className="bg-linear-surface-1 border border-linear-hairline rounded-2xl overflow-hidden shadow-sm animate-fade-cascade">
      <div className="px-6 py-5 border-b border-linear-hairline bg-linear-surface-2/40 flex items-center justify-between">
        <div className="flex items-center space-x-3">
          <div className="p-2 bg-grafana-blue/10 rounded-lg border border-grafana-blue/20">
            <Database className="w-5 h-5 text-grafana-blue" />
          </div>
          <div>
            <h3 className="text-base font-semibold text-linear-ink">Database Engine Telemetry</h3>
            <p className="text-xs text-linear-ink-muted mt-0.5">Live metrics from pg_stat_database & pg_stat_user_tables</p>
          </div>
        </div>
        <div className="flex items-center space-x-3">
          <RefreshButton
            onRefresh={() => refetch()}
            variant="icon-dark"
            title="Refresh metrics"
          />
          <span className="inline-flex items-center space-x-1.5 px-2.5 py-1 bg-linear-success/10 text-linear-success text-xs font-medium rounded-md border border-linear-success/20">
            <div className="w-1.5 h-1.5 bg-linear-success rounded-full animate-pulse" />
            <span>PostgreSQL Active</span>
          </span>
        </div>
      </div>

      {/* High-level metrics */}
      <div className="grid grid-cols-3 divide-x divide-linear-hairline border-b border-linear-hairline">
        <div className="p-5 flex flex-col items-center text-center">
          <Zap className="w-5 h-5 text-amber-400 mb-2 opacity-80" />
          {isLoading ? (
            <Loader2 className="w-6 h-6 text-linear-ink-muted animate-fast-spin" />
          ) : (
            <span className="text-2xl font-bold font-mono text-linear-ink">{data?.cache_hit_rate ?? 0}%</span>
          )}
          <span className="text-xs text-linear-ink-muted uppercase font-semibold mt-1">Buffer Cache Hit</span>
        </div>
        <div className="p-5 flex flex-col items-center text-center">
          <HardDrive className="w-5 h-5 text-grafana-blue mb-2 opacity-80" />
          {isLoading ? (
            <Loader2 className="w-6 h-6 text-linear-ink-muted animate-fast-spin" />
          ) : (
            <span className="text-2xl font-bold font-mono text-linear-ink">{data?.db_size ?? 'N/A'}</span>
          )}
          <span className="text-xs text-linear-ink-muted uppercase font-semibold mt-1">Database Size</span>
        </div>
        <div className="p-5 flex flex-col items-center text-center">
          <Table className="w-5 h-5 text-linear-primary mb-2 opacity-80" />
          {isLoading ? (
            <Loader2 className="w-6 h-6 text-linear-ink-muted animate-fast-spin" />
          ) : (
            <span className="text-2xl font-bold font-mono text-linear-ink">{data?.audit_log_size ?? 'N/A'}</span>
          )}
          <span className="text-xs text-linear-ink-muted uppercase font-semibold mt-1">Audit Log Relation</span>
        </div>
      </div>

      {/* Table Stats */}
      <div className="overflow-x-auto">
        <table className="w-full text-xs text-left">
          <thead className="bg-linear-surface-2/80 text-[11px] text-linear-ink-muted uppercase tracking-wider border-b border-linear-hairline">
            <tr>
              <th className="px-4 py-2.5 font-medium">Table</th>
              <th className="px-4 py-2.5 font-medium">Seq Scans</th>
              <th className="px-4 py-2.5 font-medium">Index Scans</th>
              <th className="px-4 py-2.5 font-medium">Inserts</th>
              <th className="px-4 py-2.5 font-medium">Updates</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-linear-hairline/60">
            {isLoading ? (
              <tr>
                <td colSpan={5} className="px-4 py-8 text-center text-linear-ink-muted">
                  <Loader2 className="w-5 h-5 text-linear-ink-muted animate-fast-spin inline mr-2" />
                  Reading pg_stat_user_tables...
                </td>
              </tr>
            ) : isError || !data?.table_stats || data.table_stats.length === 0 ? (
              <tr>
                <td colSpan={5} className="px-4 py-8 text-center text-linear-ink-subtle">
                  No table statistics available.
                </td>
              </tr>
            ) : (
              data.table_stats.map((stat) => (
                <tr key={stat.table_name} className="hover:bg-linear-surface-2/40 transition-colors group">
                  <td className="px-4 py-2.5 font-mono text-xs text-linear-ink">
                    <code className="text-linear-primary bg-linear-primary/10 border border-linear-primary/20 px-1.5 py-0.5 rounded">
                      {stat.table_name}
                    </code>
                  </td>
                  <td className="px-4 py-2.5 text-linear-ink-muted font-mono text-xs">
                    {stat.seq_scans.toLocaleString()}
                  </td>
                  <td className="px-4 py-2.5 text-linear-ink font-mono text-xs">
                    <span className="text-linear-success">{stat.idx_scans.toLocaleString()}</span>
                  </td>
                  <td className="px-4 py-2.5 text-linear-ink font-mono text-xs">
                    {stat.inserts.toLocaleString()}
                  </td>
                  <td className="px-4 py-2.5 text-linear-ink font-mono text-xs">
                    {stat.updates.toLocaleString()}
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      <div className="px-6 py-3 bg-linear-surface-2/30 border-t border-linear-hairline text-xs text-linear-ink-subtle flex items-center justify-between">
        <span>Source: PostgreSQL pg_stat_user_tables</span>
        <span>Real-time engine telemetry</span>
      </div>
    </div>
  );
}
