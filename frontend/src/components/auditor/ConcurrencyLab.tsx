import { useState, useEffect, useRef } from 'react';
import { useAuth } from '@clerk/clerk-react';
import { Activity, Play, Settings2, AlertOctagon } from 'lucide-react';
import { runConcurrencyTest } from '../../services/auditService';
import Button from '../common/Button';

interface SimulationLog {
  id: string;
  txId: string;
  workerId: number;
  action: string;
  status: 'pending' | 'success' | 'error';
  timestamp: Date;
}

export default function ConcurrencyLab() {
  const { getToken } = useAuth();
  const [workers, setWorkers] = useState<number>(5);
  const [isRunning, setIsRunning] = useState(false);
  const [logs, setLogs] = useState<SimulationLog[]>([]);
  const [stats, setStats] = useState({ success: 0, failed: 0, total: 0 });
  const logsEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (logsEndRef.current) {
      logsEndRef.current.scrollIntoView({ behavior: 'smooth' });
    }
  }, [logs]);

  const runSimulation = async () => {
    if (isRunning) return;
    setIsRunning(true);
    setLogs([]);
    setStats({ success: 0, failed: 0, total: 0 });

    try {
      const result = await runConcurrencyTest(workers, () => getToken());
      
      const mappedLogs: SimulationLog[] = result.logs.map((item, idx) => ({
        id: `${item.tx_id}-${idx}`,
        txId: item.tx_id,
        workerId: item.worker_id,
        action: item.sequence_id
          ? `${item.action} (seq #${item.sequence_id}, ${item.latency_ms}ms)`
          : `${item.action} (${item.latency_ms}ms)`,
        status: item.status as 'pending' | 'success' | 'error',
        timestamp: new Date(item.timestamp || Date.now()),
      }));

      setLogs(mappedLogs);
      setStats({
        success: result.success_count,
        failed: result.failed_count,
        total: result.workers,
      });
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Concurrency test failed';
      setLogs([{
        id: 'err-1',
        txId: 'ERR',
        workerId: 0,
        action: `Execution Error: ${msg}`,
        status: 'error',
        timestamp: new Date(),
      }]);
      setStats({ success: 0, failed: workers, total: workers });
    } finally {
      setIsRunning(false);
    }
  };

  return (
    <div className="space-y-6 animate-fade-cascade mt-6">
      <div className="bg-linear-surface-1 border border-linear-hairline rounded-2xl p-6 flex flex-col justify-center relative overflow-hidden shadow-sm">
        <h2 className="text-xl font-bold text-linear-ink flex items-center space-x-2">
          <Activity className="w-6 h-6 text-linear-primary" />
          <span>Concurrency Lab</span>
        </h2>
        <p className="text-linear-ink-muted text-sm mt-2 max-w-xl">
          Simulate high-concurrency environments to test transaction isolation, locking behaviors, and tamper-evident guarantees under stress.
        </p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Controls */}
        <div className="bg-linear-surface-1 border border-linear-hairline rounded-2xl overflow-hidden shadow-sm">
          <div className="px-6 py-4 border-b border-linear-hairline bg-linear-surface-2/40 flex items-center space-x-2">
            <Settings2 className="w-5 h-5 text-linear-ink-muted" />
            <h3 className="font-semibold text-linear-ink">Simulation Controls</h3>
          </div>
          <div className="p-6 space-y-6">
            <div>
              <label className="block text-sm font-medium text-linear-ink-muted mb-2">
                Concurrent Workers: <span className="text-linear-primary font-mono">{workers}</span>
              </label>
              <input 
                type="range" 
                min="1" 
                max="50" 
                value={workers} 
                onChange={(e) => setWorkers(parseInt(e.target.value))}
                disabled={isRunning}
                className="w-full accent-linear-primary cursor-pointer"
              />
              <div className="flex justify-between text-xs text-linear-ink-subtle mt-1">
                <span>1</span>
                <span>50</span>
              </div>
            </div>

            <div className="bg-linear-canvas p-3 rounded-lg border border-linear-hairline text-xs text-linear-ink-muted space-y-1">
              <p className="font-semibold text-linear-ink">Execution Strategy:</p>
              <p>Concurrent async workers dispatched simultaneously against PostgreSQL with row-level transaction verification.</p>
            </div>

            <Button
              type="button"
              variant="primary"
              size="lg"
              portalTheme="auditor"
              loading={isRunning}
              disabled={isRunning}
              onClick={runSimulation}
              leftIcon={<Play className="w-4 h-4" />}
              className="w-full !rounded-xl font-semibold"
            >
              {isRunning ? 'Running Simulation...' : 'Start Simulation'}
            </Button>

            {stats.total > 0 && !isRunning && (
              <div className="pt-4 border-t border-linear-hairline grid grid-cols-2 gap-4">
                <div className="bg-linear-success/10 border border-linear-success/20 p-3 rounded-lg text-center">
                  <span className="block text-2xl font-bold font-mono text-linear-success">{stats.success}</span>
                  <span className="text-[10px] uppercase font-bold text-linear-success tracking-wider">Success</span>
                </div>
                <div className="bg-grafana-orange/10 border border-grafana-orange/20 p-3 rounded-lg text-center">
                  <span className="block text-2xl font-bold font-mono text-grafana-orange">{stats.failed}</span>
                  <span className="text-[10px] uppercase font-bold text-grafana-orange tracking-wider">Serialization Failures</span>
                </div>
              </div>
            )}
          </div>
        </div>

        {/* Live Logs */}
        <div className="lg:col-span-2 bg-linear-surface-1 border border-linear-hairline rounded-2xl overflow-hidden shadow-sm flex flex-col">
          <div className="px-6 py-4 border-b border-linear-hairline bg-linear-surface-2/40 flex items-center justify-between">
            <h3 className="font-semibold text-linear-ink">Live Execution Log</h3>
            {isRunning && (
              <span className="flex items-center space-x-2 text-xs font-medium text-linear-success bg-linear-success/10 px-2 py-1 rounded border border-linear-success/20">
                <span className="w-2 h-2 rounded-full bg-linear-success animate-pulse" />
                <span>Simulating...</span>
              </span>
            )}
          </div>
          
          <div className="flex-1 p-4 bg-linear-canvas font-mono text-xs overflow-y-auto min-h-[400px] max-h-[500px]">
            {logs.length === 0 ? (
              <div className="h-full flex flex-col items-center justify-center text-linear-ink-subtle space-y-3">
                <AlertOctagon className="w-8 h-8 opacity-50" />
                <p>No active simulations. Adjust controls and click Start.</p>
              </div>
            ) : (
              <div className="space-y-2">
                {logs.map((log) => (
                  <div key={log.id} className="flex space-x-3 text-linear-ink">
                    <span className="text-linear-ink-subtle flex-shrink-0">
                      {log.timestamp.toISOString().split('T')[1].substring(0, 12)}
                    </span>
                    <span className="text-linear-primary flex-shrink-0 w-16">
                      [W-{log.workerId.toString().padStart(2, '0')}]
                    </span>
                    <span className="text-grafana-blue flex-shrink-0 w-16">
                      {log.txId}
                    </span>
                    <span className={`flex-1 break-words ${
                      log.status === 'success' ? 'text-linear-success' :
                      log.status === 'error' ? 'text-grafana-orange' : 'text-linear-ink-muted'
                    }`}>
                      {log.action}
                    </span>
                  </div>
                ))}
                <div ref={logsEndRef} />
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
