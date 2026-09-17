import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { useAuth } from '@clerk/clerk-react';
import { useNavigate } from 'react-router-dom';
import {
  Users,
  ShieldCheck,
  AlertTriangle,
  Clock,
  Activity,
  Database,
  ExternalLink,
} from 'lucide-react';
import { fetchDashboardStats, type DashboardStats } from '../../services/auditService';
import RefreshButton from '../../components/common/RefreshButton';
import { LiveStreamBadge } from '../../components/common/LiveStreamBadge';
import { Button } from '../../components/common/Button';

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
  INSERT: 'bg-linear-success/10 text-linear-success border-linear-success/30',
  UPDATE: 'bg-grafana-blue/10 text-grafana-blue border-grafana-blue/30',
  DELETE: 'bg-grafana-orange/10 text-grafana-orange border-grafana-orange/30',
};

export default function Dashboard() {
  const { getToken } = useAuth();
  const navigate = useNavigate();
  const [isStreaming, setIsStreaming] = useState(true);

  const { data, isLoading, isError, dataUpdatedAt, refetch } = useQuery<DashboardStats>({
    queryKey: ['dashboardStats'],
    queryFn: () => fetchDashboardStats(() => getToken()),
    refetchInterval: isStreaming ? 3000 : false,
  });

  return (
    <div className="space-y-6 animate-fade-cascade">
      {/* Header Bar */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 pb-1">
        <div>
          <div className="flex items-center gap-2.5">
            <h1 className="text-xl font-bold text-grafana-ink tracking-tight">
              Workforce Telemetry & Operations
            </h1>
            <span className="hidden sm:inline-flex items-center gap-1 px-2 py-0.5 rounded text-[11px] font-mono font-semibold bg-grafana-surface border border-grafana-border text-grafana-neutral">
              <Database className="w-3 h-3 text-grafana-neutral" />
              Live Replication
            </span>
          </div>
          <p className="text-grafana-neutral text-xs mt-1">
            Real-time workforce headcount, cryptographic integrity status, and trigger mutation stream.
          </p>
        </div>

        <div className="flex items-center gap-3">
          <LiveStreamBadge
            isStreaming={isStreaming}
            onToggleStream={() => setIsStreaming(!isStreaming)}
            lastFetchedAt={dataUpdatedAt}
            portalTheme="hr"
          />
          <RefreshButton
            onRefresh={() => refetch()}
            label="Refresh Metrics"
            variant="light"
            title="Force refresh workforce telemetry"
          />
        </div>
      </div>

      {/* Metrics Row — Grafana Enterprise Telemetry Panels */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-5">
        {/* Total Active Employees */}
        <div className="bg-white rounded-xl border border-grafana-border border-t-2 border-t-grafana-blue p-5 flex flex-col justify-between shadow-2xs">
          <div className="flex items-center justify-between">
            <span className="text-[11px] font-bold uppercase tracking-wider text-grafana-neutral font-mono">
              Active Workforce
            </span>
            <div className="p-2 bg-grafana-blue/10 text-grafana-blue rounded-lg border border-grafana-blue/20">
              <Users className="w-4 h-4" />
            </div>
          </div>
          <div className="mt-4">
            {isLoading ? (
              <div className="h-9 w-24 bg-grafana-surface animate-pulse rounded-md" />
            ) : (
              <p className="text-3xl font-black text-grafana-ink tracking-tight font-mono tabular-nums">
                {data?.active_employees ?? 0}
              </p>
            )}
            <div className="mt-3 flex items-center justify-between pt-3 border-t border-grafana-border text-xs">
              <span className="text-grafana-neutral">Total Profiles Enrolled</span>
              <span className="font-semibold text-grafana-ink font-mono bg-grafana-surface px-2 py-0.5 rounded border border-grafana-border">
                {data?.total_employees ?? 0}
              </span>
            </div>
          </div>
        </div>

        {/* Total Audit Events */}
        <div className="bg-white rounded-xl border border-grafana-border border-t-2 border-t-linear-success p-5 flex flex-col justify-between shadow-2xs">
          <div className="flex items-center justify-between">
            <span className="text-[11px] font-bold uppercase tracking-wider text-grafana-neutral font-mono">
              Audit Chain Ledger
            </span>
            <div className="p-2 bg-linear-success/10 text-linear-success rounded-lg border border-linear-success/20">
              <ShieldCheck className="w-4 h-4" />
            </div>
          </div>
          <div className="mt-4">
            {isLoading ? (
              <div className="h-9 w-24 bg-grafana-surface animate-pulse rounded-md" />
            ) : (
              <p className="text-3xl font-black text-grafana-ink tracking-tight font-mono tabular-nums">
                {data?.total_audit_events ?? 0}
              </p>
            )}
            <div className="mt-3 flex items-center justify-between pt-3 border-t border-grafana-border text-xs">
              <span className="text-linear-success font-medium flex items-center gap-1.5">
                <span className="w-2 h-2 rounded-full bg-linear-success animate-pulse" />
                Trigger Sealed
              </span>
              <span className="font-semibold text-linear-success font-mono bg-linear-success/10 px-2 py-0.5 rounded border border-linear-success/20">
                100% Intact
              </span>
            </div>
          </div>
        </div>

        {/* Suspicious Flags */}
        <div className="bg-white rounded-xl border border-grafana-border border-t-2 border-t-grafana-orange p-5 flex flex-col justify-between shadow-2xs">
          <div className="flex items-center justify-between">
            <span className="text-[11px] font-bold uppercase tracking-wider text-grafana-neutral font-mono">
              Compliance Alerts
            </span>
            <div
              className={`p-2 rounded-lg border ${
                (data?.unreviewed_flags ?? 0) > 0
                  ? 'bg-grafana-orange/10 text-grafana-orange border-grafana-orange/30'
                  : 'bg-grafana-surface text-grafana-neutral border-grafana-border'
              }`}
            >
              <AlertTriangle className="w-4 h-4" />
            </div>
          </div>
          <div className="mt-4">
            {isLoading ? (
              <div className="h-9 w-24 bg-grafana-surface animate-pulse rounded-md" />
            ) : (
              <p className="text-3xl font-black text-grafana-ink tracking-tight font-mono tabular-nums">
                {data?.unreviewed_flags ?? 0}
              </p>
            )}
            <div className="mt-3 flex items-center justify-between pt-3 border-t border-grafana-border text-xs">
              <span className="text-grafana-neutral">Unreviewed Anomaly Flags</span>
              <span
                className={`font-semibold font-mono px-2 py-0.5 rounded ${
                  (data?.unreviewed_flags ?? 0) > 0
                    ? 'bg-grafana-orange/10 text-grafana-orange border border-grafana-orange/30'
                    : 'bg-grafana-surface text-grafana-neutral border border-grafana-border'
                }`}
              >
                {(data?.unreviewed_flags ?? 0) > 0 ? 'Requires Review' : '0 Anomalies'}
              </span>
            </div>
          </div>
        </div>
      </div>

      {/* Live Recent Activity Stream */}
      <div className="bg-white rounded-xl border border-grafana-border shadow-2xs overflow-hidden">
        <div className="p-4 border-b border-grafana-border flex items-center justify-between bg-grafana-surface">
          <div className="flex items-center gap-2.5">
            <div className="p-1.5 rounded-lg bg-grafana-blue/10 text-grafana-blue border border-grafana-blue/20">
              <Activity className="w-4 h-4" />
            </div>
            <div>
              <h2 className="text-sm font-bold text-grafana-ink tracking-tight">
                Live Mutation Stream
              </h2>
              <p className="text-[11px] text-grafana-neutral">
                Real-time trigger events emitted directly from <code className="font-mono text-black">audit_log</code>
              </p>
            </div>
          </div>

          <div className="flex items-center gap-2">
            <span className="text-[10px] font-mono text-grafana-neutral bg-white px-2 py-1 rounded border border-grafana-border flex items-center gap-1.5 shadow-2xs">
              <span className="w-1.5 h-1.5 rounded-full bg-linear-success animate-pulse" />
              <span>pg_notify / polling 3s</span>
            </span>
          </div>
        </div>

        {isLoading ? (
          <div className="p-4 space-y-2.5">
            {[1, 2, 3, 4].map((i) => (
              <div key={i} className="h-10 bg-grafana-surface animate-pulse rounded-lg border border-grafana-border/50" />
            ))}
          </div>
        ) : isError ? (
          <div className="p-12 text-center text-xs text-grafana-orange font-mono">
            Unable to stream live activity from PostgreSQL engine.
          </div>
        ) : !data?.recent_activity || data.recent_activity.length === 0 ? (
          <div className="p-12 text-center text-xs text-grafana-neutral">
            No mutation events logged yet.
          </div>
        ) : (
          <div className="divide-y divide-grafana-border">
            {data.recent_activity.map((activity) => (
              <div
                key={activity.sequence_id}
                className="py-3 px-4 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 hover:bg-grafana-surface/70 transition-colors duration-150"
              >
                <div className="flex items-center gap-3">
                  <span className="font-mono text-xs font-bold text-grafana-neutral bg-grafana-surface px-2 py-0.5 rounded border border-grafana-border">
                    #{activity.sequence_id.toString().padStart(4, '0')}
                  </span>
                  <span
                    className={`text-[10px] font-bold uppercase tracking-wider px-2 py-0.5 rounded border ${
                      ACTION_COLORS[activity.action] || 'bg-grafana-surface text-grafana-neutral border-grafana-border'
                    }`}
                  >
                    {activity.action}
                  </span>
                  <div className="text-xs">
                    <span className="font-bold text-grafana-ink">{activity.actor_name}</span>
                    <span className="text-grafana-neutral mx-1">on</span>
                    <code className="font-mono text-xs font-semibold text-grafana-blue bg-grafana-blue/10 px-1.5 py-0.5 rounded border border-grafana-blue/20">
                      {activity.table_name}
                    </code>
                  </div>
                </div>

                <div className="text-[11px] font-mono text-grafana-neutral flex items-center gap-1.5 pl-14 sm:pl-0">
                  <Clock className="w-3 h-3 text-grafana-neutral" />
                  <span>{formatRelativeTime(activity.created_at)}</span>
                </div>
              </div>
            ))}
          </div>
        )}

        <div className="p-3 bg-grafana-surface/50 border-t border-grafana-border flex items-center justify-between text-xs">
          <span className="text-grafana-neutral text-[11px]">
            Showing latest mutations from PostgreSQL audit chain
          </span>
          <Button
            variant="link"
            portalTheme="hr"
            onClick={() => navigate('/auditor/chain')}
            rightIcon={<ExternalLink className="w-3 h-3" />}
            className="text-xs font-semibold"
          >
            Open Auditor Chain Explorer
          </Button>
        </div>
      </div>
    </div>
  );
}
