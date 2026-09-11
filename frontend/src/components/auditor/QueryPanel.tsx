import { Database, Zap, HardDrive, Clock } from 'lucide-react';

const MOCK_QUERY_STATS = [
  { id: 1, query: 'SELECT * FROM audit_log ORDER BY sequence_id DESC', calls: 14502, avgTime: '12ms', cacheHit: '98%' },
  { id: 2, query: 'SELECT check_chain_integrity()', calls: 320, avgTime: '450ms', cacheHit: '0%' },
  { id: 3, query: 'INSERT INTO audit_log (action, table_name...)', calls: 890, avgTime: '4ms', cacheHit: 'N/A' },
  { id: 4, query: 'SELECT * FROM suspicious_activity_flags', calls: 1205, avgTime: '8ms', cacheHit: '95%' },
];

export default function QueryPanel() {
  return (
    <div className="bg-slate-900/50 border border-slate-700/50 rounded-2xl overflow-hidden shadow-xl shadow-black/20 animate-in fade-in slide-in-from-bottom-4 duration-500 delay-100">
      
      <div className="px-6 py-5 border-b border-slate-700/50 bg-slate-900/80 flex items-center justify-between">
        <div className="flex items-center space-x-3">
          <div className="p-2 bg-blue-500/10 rounded-lg">
            <Database className="w-5 h-5 text-blue-400" />
          </div>
          <div>
            <h3 className="text-base font-semibold text-slate-200">Database Performance</h3>
            <p className="text-xs text-slate-400 mt-0.5">Query stats & index usage (pg_stat_statements)</p>
          </div>
        </div>
        <div className="flex space-x-2">
           <span className="inline-flex items-center space-x-1 px-2.5 py-1 bg-emerald-500/10 text-emerald-400 text-xs font-medium rounded border border-emerald-500/20">
             <div className="w-1.5 h-1.5 bg-emerald-400 rounded-full animate-pulse" />
             <span>Connected</span>
           </span>
        </div>
      </div>

      {/* High-level metrics */}
      <div className="grid grid-cols-3 divide-x divide-slate-800 border-b border-slate-800">
        <div className="p-5 flex flex-col items-center text-center">
          <Zap className="w-5 h-5 text-amber-400 mb-2 opacity-80" />
          <span className="text-2xl font-bold text-slate-200">14.2ms</span>
          <span className="text-xs text-slate-500 uppercase font-semibold mt-1">Avg Query Latency</span>
        </div>
        <div className="p-5 flex flex-col items-center text-center">
          <HardDrive className="w-5 h-5 text-blue-400 mb-2 opacity-80" />
          <span className="text-2xl font-bold text-slate-200">94.5%</span>
          <span className="text-xs text-slate-500 uppercase font-semibold mt-1">Index Hit Rate</span>
        </div>
        <div className="p-5 flex flex-col items-center text-center">
          <Clock className="w-5 h-5 text-violet-400 mb-2 opacity-80" />
          <span className="text-2xl font-bold text-slate-200">1,240</span>
          <span className="text-xs text-slate-500 uppercase font-semibold mt-1">TPS (Peak)</span>
        </div>
      </div>

      {/* Query Table */}
      <div className="overflow-x-auto">
        <table className="w-full text-sm text-left">
          <thead className="bg-slate-900/40 text-xs text-slate-500 uppercase tracking-wider border-b border-slate-800">
            <tr>
              <th className="px-6 py-3 font-medium">Query Pattern</th>
              <th className="px-6 py-3 font-medium">Total Calls</th>
              <th className="px-6 py-3 font-medium">Avg Latency</th>
              <th className="px-6 py-3 font-medium">Cache Hit</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-800/60">
            {MOCK_QUERY_STATS.map((stat) => (
              <tr key={stat.id} className="hover:bg-slate-800/30 transition-colors group">
                <td className="px-6 py-3.5 font-mono text-xs text-slate-300 truncate max-w-sm" title={stat.query}>
                  {stat.query}
                </td>
                <td className="px-6 py-3.5 text-slate-400">
                  {stat.calls.toLocaleString()}
                </td>
                <td className="px-6 py-3.5">
                  <span className={`px-2 py-0.5 rounded text-xs font-medium ${
                    parseInt(stat.avgTime) > 100 ? 'bg-amber-500/10 text-amber-400 border border-amber-500/20' : 'text-slate-400'
                  }`}>
                    {stat.avgTime}
                  </span>
                </td>
                <td className="px-6 py-3.5 text-slate-400">
                  {stat.cacheHit}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="px-6 py-3 bg-slate-900/60 border-t border-slate-800 text-xs text-slate-500 text-right">
        Stats aggregated over the last 24 hours.
      </div>
    </div>
  );
}
