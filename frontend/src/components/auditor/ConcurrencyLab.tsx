import { useState, useEffect, useRef } from 'react';
import { useAuth } from '@clerk/clerk-react';
import { Activity, Play, Settings2, AlertOctagon } from 'lucide-react';
import { runConcurrencyTest } from '../../services/auditService';

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
    <div className="space-y-6 animate-in fade-in slide-in-from-bottom-4 duration-500 mt-6">
      <div className="bg-slate-900/40 border border-slate-700/50 rounded-2xl p-6 flex flex-col justify-center relative overflow-hidden">
        <div className="absolute -top-24 -left-24 w-64 h-64 bg-blue-600/10 blur-[80px] rounded-full pointer-events-none" />
        
        <h2 className="text-xl font-bold text-slate-100 flex items-center space-x-2">
          <Activity className="w-6 h-6 text-blue-400" />
          <span>Concurrency Lab</span>
        </h2>
        <p className="text-slate-400 text-sm mt-2 max-w-xl">
          Simulate high-concurrency environments to test transaction isolation, locking behaviors, and tamper-evident guarantees under stress.
        </p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Controls */}
        <div className="bg-slate-900/50 border border-slate-700/50 rounded-2xl overflow-hidden shadow-xl shadow-black/20">
          <div className="px-6 py-4 border-b border-slate-700/50 bg-slate-900/80 flex items-center space-x-2">
            <Settings2 className="w-5 h-5 text-slate-400" />
            <h3 className="font-semibold text-slate-200">Simulation Controls</h3>
          </div>
          <div className="p-6 space-y-6">
            <div>
              <label className="block text-sm font-medium text-slate-300 mb-2">
                Concurrent Workers: <span className="text-blue-400 font-mono">{workers}</span>
              </label>
              <input 
                type="range" 
                min="1" 
                max="50" 
                value={workers} 
                onChange={(e) => setWorkers(parseInt(e.target.value))}
                disabled={isRunning}
                className="w-full accent-blue-500 cursor-pointer"
              />
              <div className="flex justify-between text-xs text-slate-500 mt-1">
                <span>1</span>
                <span>50</span>
              </div>
            </div>

            <div className="bg-slate-950/60 p-3 rounded-lg border border-slate-800 text-xs text-slate-400 space-y-1">
              <p className="font-semibold text-slate-300">Execution Strategy:</p>
              <p>Concurrent async workers dispatched simultaneously against PostgreSQL with row-level transaction verification.</p>
            </div>

            <button
              onClick={runSimulation}
              disabled={isRunning}
              className="w-full flex items-center justify-center space-x-2 bg-blue-600 hover:bg-blue-500 disabled:bg-slate-800 disabled:text-slate-500 text-white py-3 px-4 rounded-xl font-semibold transition-all shadow-[0_0_15px_rgba(37,99,235,0.3)] hover:shadow-[0_0_20px_rgba(37,99,235,0.5)] disabled:shadow-none"
            >
              {isRunning ? (
                <div className="w-5 h-5 border-2 border-white/30 border-t-white rounded-full animate-spin" />
              ) : (
                <Play className="w-5 h-5" />
              )}
              <span>{isRunning ? 'Running Simulation...' : 'Start Simulation'}</span>
            </button>

            {stats.total > 0 && !isRunning && (
              <div className="pt-4 border-t border-slate-800 grid grid-cols-2 gap-4">
                <div className="bg-emerald-500/10 border border-emerald-500/20 p-3 rounded-lg text-center">
                  <span className="block text-2xl font-bold text-emerald-400">{stats.success}</span>
                  <span className="text-[10px] uppercase font-bold text-emerald-500 tracking-wider">Success</span>
                </div>
                <div className="bg-rose-500/10 border border-rose-500/20 p-3 rounded-lg text-center">
                  <span className="block text-2xl font-bold text-rose-400">{stats.failed}</span>
                  <span className="text-[10px] uppercase font-bold text-rose-500 tracking-wider">Serialization Failures</span>
                </div>
              </div>
            )}
          </div>
        </div>

        {/* Live Logs */}
        <div className="lg:col-span-2 bg-slate-900/50 border border-slate-700/50 rounded-2xl overflow-hidden shadow-xl shadow-black/20 flex flex-col">
          <div className="px-6 py-4 border-b border-slate-700/50 bg-slate-900/80 flex items-center justify-between">
            <h3 className="font-semibold text-slate-200">Live Execution Log</h3>
            {isRunning && (
              <span className="flex items-center space-x-2 text-xs font-medium text-emerald-400 bg-emerald-500/10 px-2 py-1 rounded border border-emerald-500/20">
                <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
                <span>Simulating...</span>
              </span>
            )}
          </div>
          
          <div className="flex-1 p-4 bg-slate-950 font-mono text-xs overflow-y-auto min-h-[400px] max-h-[500px]">
            {logs.length === 0 ? (
              <div className="h-full flex flex-col items-center justify-center text-slate-600 space-y-3">
                <AlertOctagon className="w-8 h-8 opacity-50" />
                <p>No active simulations. Adjust controls and click Start.</p>
              </div>
            ) : (
              <div className="space-y-2">
                {logs.map((log) => (
                  <div key={log.id} className="flex space-x-3 text-slate-300">
                    <span className="text-slate-600 flex-shrink-0">
                      {log.timestamp.toISOString().split('T')[1].substring(0, 12)}
                    </span>
                    <span className="text-violet-400 flex-shrink-0 w-16">
                      [W-{log.workerId.toString().padStart(2, '0')}]
                    </span>
                    <span className="text-blue-400 flex-shrink-0 w-16">
                      {log.txId}
                    </span>
                    <span className={`flex-1 break-words ${
                      log.status === 'success' ? 'text-emerald-400' :
                      log.status === 'error' ? 'text-rose-400' : 'text-slate-400'
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
