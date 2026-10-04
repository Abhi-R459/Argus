import React, { useState, useEffect } from 'react';
import { useAuth } from '@clerk/clerk-react';
import {
  GitCompare, Play, AlertCircle, ShieldCheck,
  TrendingDown, DollarSign, Clock, Sparkles,
  RefreshCw, AlertTriangle
} from 'lucide-react';
import {
  runCounterfactualSimulation,
  fetchEmployees,
  CounterfactualResult,
  EmployeeListItem,
} from '../../services/auditService';

export default function CounterfactualPage() {
  const { getToken } = useAuth();

  // Inputs
  const [employeeId, setEmployeeId] = useState<number>(1);
  const [skipSeqInput, setSkipSeqInput] = useState<string>('71');
  const [asOfInput, setAsOfInput] = useState<string>('');
  
  // State
  const [employees, setEmployees] = useState<EmployeeListItem[]>([]);
  const [isSimulating, setIsSimulating] = useState(false);
  const [result, setResult] = useState<CounterfactualResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  // Fetch initial employee directory for easy selection
  useEffect(() => {
    let isMounted = true;
    async function loadDirectory() {
      try {
        const data = await fetchEmployees(getToken, 20);
        if (isMounted && data.items.length > 0) {
          setEmployees(data.items);
          setEmployeeId(data.items[0].employee_id);
        }
      } catch {
        // Non-fatal; user can still manually input numeric ID
      }
    }
    loadDirectory();
    return () => { isMounted = false; };
  }, [getToken]);

  const handleRunSimulation = async (e?: React.FormEvent) => {
    if (e) e.preventDefault();
    setError(null);

    // Parse skip sequence IDs
    const parsedIds = skipSeqInput
      .split(',')
      .map((s) => parseInt(s.trim(), 10))
      .filter((n) => !isNaN(n));

    if (parsedIds.length === 0) {
      setError('Please provide at least one valid sequence ID to exclude.');
      return;
    }

    let formattedAsOf: string | undefined = undefined;
    if (asOfInput.trim()) {
      const parsedDate = new Date(asOfInput.trim());
      if (isNaN(parsedDate.getTime())) {
        setError('Please enter a valid ISO date/time format for the simulation horizon.');
        return;
      }
      formattedAsOf = parsedDate.toISOString();
    }

    setIsSimulating(true);
    try {
      const res = await runCounterfactualSimulation(
        {
          employee_id: Number(employeeId),
          skip_sequence_ids: parsedIds,
          as_of: formattedAsOf,
        },
        getToken,
      );
      setResult(res);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err);
      setError(msg || 'Simulation failed. Check sequence IDs and employee ID.');
    } finally {
      setIsSimulating(false);
    }
  };

  return (
    <div className="space-y-6 max-w-7xl mx-auto pb-12">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-linear-hairline pb-5">
        <div>
          <div className="flex items-center gap-2.5">
            <div className="p-2 rounded-lg bg-linear-primary/15 text-linear-primary border border-linear-primary/30">
              <GitCompare className="w-5 h-5" />
            </div>
            <div>
              <h1 className="text-xl font-bold tracking-tight text-linear-ink">
                Counterfactual "What-If" Provenance Replay
              </h1>
              <p className="text-xs text-linear-ink-subtle mt-0.5">
                Simulate alternative historical outcomes by skipping designated anomalous mutations without modifying the tamper-evident hash chain.
              </p>
            </div>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <span className="text-[11px] font-semibold px-2.5 py-1 rounded-full bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 flex items-center gap-1.5">
            <Sparkles className="w-3.5 h-3.5" />
            Novelty 11 · Prescriptive Simulation
          </span>
          <span className="text-[11px] font-semibold px-2.5 py-1 rounded-full bg-linear-surface-2 text-linear-ink-subtle border border-linear-hairline flex items-center gap-1.5">
            <ShieldCheck className="w-3.5 h-3.5 text-linear-primary" />
            Read-Only Replay
          </span>
        </div>
      </div>

      {/* Control Panel Card */}
      <div className="bg-linear-surface-1 border border-linear-hairline rounded-xl p-5 shadow-xs">
        <form onSubmit={handleRunSimulation} className="space-y-4">
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            {/* Employee Selector */}
            <div>
              <label className="block text-xs font-semibold text-linear-ink-subtle uppercase tracking-wider mb-1.5">
                Target Personnel
              </label>
              {employees.length > 0 ? (
                <select
                  value={employeeId}
                  onChange={(e) => setEmployeeId(Number(e.target.value))}
                  className="w-full text-sm bg-linear-surface-2 border border-linear-hairline rounded-lg px-3 py-2 text-linear-ink focus:outline-hidden focus:border-linear-primary"
                >
                  {employees.map((emp) => (
                    <option key={emp.employee_id} value={emp.employee_id}>
                      #{emp.employee_id} — {emp.full_name} ({emp.role_title || 'Employee'})
                    </option>
                  ))}
                </select>
              ) : (
                <input
                  type="number"
                  value={employeeId}
                  onChange={(e) => setEmployeeId(Number(e.target.value))}
                  placeholder="Employee ID (e.g. 42)"
                  className="w-full text-sm bg-linear-surface-2 border border-linear-hairline rounded-lg px-3 py-2 text-linear-ink focus:outline-hidden focus:border-linear-primary"
                />
              )}
            </div>

            {/* Excluded Sequence IDs */}
            <div>
              <div className="flex items-center justify-between mb-1.5">
                <label className="text-xs font-semibold text-linear-ink-subtle uppercase tracking-wider">
                  Exclude Sequence IDs
                </label>
                <span className="text-[10px] text-linear-ink-muted">Comma-separated</span>
              </div>
              <input
                type="text"
                value={skipSeqInput}
                onChange={(e) => setSkipSeqInput(e.target.value)}
                placeholder="e.g. 71, 72"
                className="w-full text-sm font-mono bg-linear-surface-2 border border-linear-hairline rounded-lg px-3 py-2 text-linear-ink focus:outline-hidden focus:border-linear-primary"
              />
            </div>

            {/* As-Of Timestamp (Optional) */}
            <div>
              <div className="flex items-center justify-between mb-1.5">
                <label className="text-xs font-semibold text-linear-ink-subtle uppercase tracking-wider">
                  As-Of Point in Time
                </label>
                <span className="text-[10px] text-linear-ink-muted">Optional (Default: Latest)</span>
              </div>
              <input
                type="datetime-local"
                value={asOfInput}
                onChange={(e) => setAsOfInput(e.target.value)}
                className="w-full text-sm bg-linear-surface-2 border border-linear-hairline rounded-lg px-3 py-2 text-linear-ink focus:outline-hidden focus:border-linear-primary"
              />
            </div>
          </div>

          {/* Quick presets & Action */}
          <div className="flex flex-wrap items-center justify-between gap-3 pt-2 border-t border-linear-hairline/60">
            <div className="flex items-center gap-2">
              <span className="text-xs text-linear-ink-muted">Quick Presets:</span>
              <button
                type="button"
                onClick={() => setSkipSeqInput('71')}
                className="text-xs px-2.5 py-1 rounded bg-linear-surface-2 hover:bg-linear-surface-3 text-linear-ink-subtle hover:text-linear-ink border border-linear-hairline transition-colors"
              >
                Seq #71 (Salary Spike)
              </button>
              <button
                type="button"
                onClick={() => setSkipSeqInput('124, 125')}
                className="text-xs px-2.5 py-1 rounded bg-linear-surface-2 hover:bg-linear-surface-3 text-linear-ink-subtle hover:text-linear-ink border border-linear-hairline transition-colors"
              >
                Seq #124, 125 (Multi-Event)
              </button>
            </div>

            <button
              type="submit"
              disabled={isSimulating}
              className="btn-press flex items-center gap-2 px-5 py-2 rounded-lg bg-linear-primary hover:bg-linear-primary/90 text-white text-sm font-semibold shadow-xs disabled:opacity-50 transition-colors duration-150"
            >
              {isSimulating ? (
                <>
                  <RefreshCw className="w-4 h-4 animate-fast-spin" />
                  <span>Simulating Replay...</span>
                </>
              ) : (
                <>
                  <Play className="w-4 h-4 fill-white" />
                  <span>Run Provenance Simulation</span>
                </>
              )}
            </button>
          </div>
        </form>
      </div>

      {/* Error Banner */}
      {error && (
        <div className="p-4 rounded-xl bg-rose-500/10 border border-rose-500/30 text-rose-300 flex items-start gap-3">
          <AlertCircle className="w-5 h-5 text-rose-400 shrink-0 mt-0.5" />
          <div>
            <h4 className="text-sm font-semibold text-rose-200">Simulation Error</h4>
            <p className="text-xs text-rose-300/90 mt-0.5">{error}</p>
          </div>
        </div>
      )}

      {/* Results View */}
      {result && (
        <div className="space-y-6">
          {/* Blast Radius Impact Cards */}
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
            <div className="bg-linear-surface-1 border border-linear-hairline rounded-xl p-4 shadow-xs">
              <div className="flex items-center justify-between text-xs text-linear-ink-subtle mb-1">
                <span>Annual Salary Delta</span>
                <TrendingDown className="w-4 h-4 text-amber-400" />
              </div>
              <div className="text-2xl font-bold text-amber-400 tracking-tight">
                ${result.blast_radius.salary_overpaid_annual.toLocaleString('en-US', { minimumFractionDigits: 2 })}
              </div>
              <p className="text-[11px] text-linear-ink-muted mt-1">
                Actual (${result.blast_radius.salary_actual.toLocaleString()}) vs Replay (${result.blast_radius.salary_counterfactual.toLocaleString()})
              </p>
            </div>

            <div className="bg-linear-surface-1 border border-linear-hairline rounded-xl p-4 shadow-xs">
              <div className="flex items-center justify-between text-xs text-linear-ink-subtle mb-1">
                <span>Cumulative Overpaid</span>
                <DollarSign className="w-4 h-4 text-rose-400" />
              </div>
              <div className="text-2xl font-bold text-rose-400 tracking-tight">
                ${result.blast_radius.salary_overpaid_cumulative.toLocaleString('en-US', { minimumFractionDigits: 2 })}
              </div>
              <p className="text-[11px] text-linear-ink-muted mt-1">
                Cumulative financial exposure over fraud tenure
              </p>
            </div>

            <div className="bg-linear-surface-1 border border-linear-hairline rounded-xl p-4 shadow-xs">
              <div className="flex items-center justify-between text-xs text-linear-ink-subtle mb-1">
                <span>Elapsed Fraud Tenure</span>
                <Clock className="w-4 h-4 text-linear-primary" />
              </div>
              <div className="text-2xl font-bold text-linear-ink tracking-tight">
                {result.blast_radius.tenure_months.toFixed(1)} <span className="text-sm font-normal text-linear-ink-subtle">months</span>
              </div>
              <p className="text-[11px] text-linear-ink-muted mt-1">
                From first excluded sequence to evaluation point
              </p>
            </div>

            <div className="bg-linear-surface-1 border border-linear-hairline rounded-xl p-4 shadow-xs">
              <div className="flex items-center justify-between text-xs text-linear-ink-subtle mb-1">
                <span>Simulation Latency</span>
                <RefreshCw className="w-4 h-4 text-emerald-400" />
              </div>
              <div className="text-2xl font-bold text-emerald-400 tracking-tight">
                {result.simulation_duration_ms.toFixed(1)} <span className="text-sm font-normal text-linear-ink-subtle">ms</span>
              </div>
              <p className="text-[11px] text-linear-ink-muted mt-1">
                {result.applied_events_count} applied, {result.blast_radius.skipped_events_count} skipped
              </p>
            </div>
          </div>

          {/* Side-by-Side Comparison Table */}
          <div className="bg-linear-surface-1 border border-linear-hairline rounded-xl overflow-hidden shadow-xs">
            <div className="px-5 py-4 border-b border-linear-hairline flex items-center justify-between">
              <div>
                <h3 className="text-sm font-bold text-linear-ink">State Divergence Analysis</h3>
                <p className="text-xs text-linear-ink-subtle">
                  Comparing unmodified historical record vs virtual counterfactual replay
                </p>
              </div>
              <span className="text-xs px-2.5 py-1 rounded-md bg-linear-surface-2 text-linear-ink-subtle border border-linear-hairline font-mono">
                Employee #{result.employee_id}
              </span>
            </div>

            <div className="overflow-x-auto">
              <table className="w-full text-left text-sm">
                <thead>
                  <tr className="border-b border-linear-hairline bg-linear-surface-2 text-linear-ink-subtle text-xs font-semibold uppercase tracking-wider">
                    <th className="py-3 px-4">Entity Attribute</th>
                    <th className="py-3 px-4">Actual Present State</th>
                    <th className="py-3 px-4">Counterfactual Replay State</th>
                    <th className="py-3 px-4">Variance / Delta</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-linear-hairline/60">
                  {/* Salary Row */}
                  <tr className="bg-amber-500/5 hover:bg-amber-500/10 transition-colors">
                    <td className="py-3 px-4 font-semibold text-linear-ink flex items-center gap-1.5">
                      <DollarSign className="w-3.5 h-3.5 text-amber-400" />
                      Compensation (Annual)
                    </td>
                    <td className="py-3 px-4 font-mono font-semibold text-linear-ink">
                      ${Number(result.actual_state?.salary || 0).toLocaleString('en-US', { minimumFractionDigits: 2 })}
                    </td>
                    <td className="py-3 px-4 font-mono font-semibold text-emerald-400">
                      ${Number(result.counterfactual_state?.salary || 0).toLocaleString('en-US', { minimumFractionDigits: 2 })}
                    </td>
                    <td className="py-3 px-4">
                      {result.blast_radius.salary_overpaid_annual > 0 ? (
                        <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-semibold bg-rose-500/20 text-rose-300 border border-rose-500/30">
                          - ${result.blast_radius.salary_overpaid_annual.toLocaleString()} / yr
                        </span>
                      ) : (
                        <span className="text-xs text-linear-ink-muted">Identical</span>
                      )}
                    </td>
                  </tr>

                  {/* Role Title */}
                  <tr className="hover:bg-linear-surface-2/40 transition-colors">
                    <td className="py-3 px-4 font-semibold text-linear-ink">Job Title / Role</td>
                    <td className="py-3 px-4 text-linear-ink-subtle">
                      {String(result.actual_state?.role_title || 'N/A')}
                    </td>
                    <td className="py-3 px-4 text-linear-ink">
                      {String(result.counterfactual_state?.role_title || 'N/A')}
                    </td>
                    <td className="py-3 px-4">
                      {result.actual_state?.role_title !== result.counterfactual_state?.role_title ? (
                        <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-semibold bg-amber-500/20 text-amber-300 border border-amber-500/30">
                          Diverged
                        </span>
                      ) : (
                        <span className="text-xs text-linear-ink-muted">Identical</span>
                      )}
                    </td>
                  </tr>

                  {/* Department */}
                  <tr className="hover:bg-linear-surface-2/40 transition-colors">
                    <td className="py-3 px-4 font-semibold text-linear-ink">Department</td>
                    <td className="py-3 px-4 text-linear-ink-subtle">
                      {String(result.actual_state?.department_name || 'N/A')}
                    </td>
                    <td className="py-3 px-4 text-linear-ink">
                      {String(result.counterfactual_state?.department_name || 'N/A')}
                    </td>
                    <td className="py-3 px-4">
                      {result.actual_state?.department_name !== result.counterfactual_state?.department_name ? (
                        <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-semibold bg-amber-500/20 text-amber-300 border border-amber-500/30">
                          Diverged
                        </span>
                      ) : (
                        <span className="text-xs text-linear-ink-muted">Identical</span>
                      )}
                    </td>
                  </tr>

                  {/* Full Name */}
                  <tr className="hover:bg-linear-surface-2/40 transition-colors">
                    <td className="py-3 px-4 font-semibold text-linear-ink">Full Name</td>
                    <td className="py-3 px-4 text-linear-ink-subtle">{String(result.actual_state?.full_name || 'N/A')}</td>
                    <td className="py-3 px-4 text-linear-ink">{String(result.counterfactual_state?.full_name || 'N/A')}</td>
                    <td className="py-3 px-4 text-xs text-linear-ink-muted">Identical</td>
                  </tr>

                  {/* Email */}
                  <tr className="hover:bg-linear-surface-2/40 transition-colors">
                    <td className="py-3 px-4 font-semibold text-linear-ink">Work Email</td>
                    <td className="py-3 px-4 text-linear-ink-subtle">{String(result.actual_state?.email || 'N/A')}</td>
                    <td className="py-3 px-4 text-linear-ink">{String(result.counterfactual_state?.email || 'N/A')}</td>
                    <td className="py-3 px-4 text-xs text-linear-ink-muted">Identical</td>
                  </tr>

                  {/* Status */}
                  <tr className="hover:bg-linear-surface-2/40 transition-colors">
                    <td className="py-3 px-4 font-semibold text-linear-ink">Employment Status</td>
                    <td className="py-3 px-4 text-linear-ink-subtle">
                      {result.actual_state?.is_active ? 'Active' : 'Inactive'}
                    </td>
                    <td className="py-3 px-4 text-linear-ink">
                      {result.counterfactual_state?.is_active ? 'Active' : 'Inactive'}
                    </td>
                    <td className="py-3 px-4 text-xs text-linear-ink-muted">Identical</td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>

          {/* Excluded Forensic Events Panel */}
          {result.skipped_events.length > 0 && (
            <div className="bg-linear-surface-1 border border-linear-hairline rounded-xl p-5 shadow-xs">
              <h3 className="text-sm font-bold text-linear-ink mb-1 flex items-center gap-2">
                <AlertTriangle className="w-4 h-4 text-amber-400" />
                Excluded Historical Audit Entries ({result.skipped_events.length})
              </h3>
              <p className="text-xs text-linear-ink-subtle mb-4">
                The following anomalous ledger events were masked during the virtual state walk:
              </p>

              <div className="space-y-2.5">
                {result.skipped_events.map((ev) => (
                  <div
                    key={ev.sequence_id}
                    className="p-3.5 rounded-lg bg-linear-surface-2 border border-linear-hairline flex flex-col sm:flex-row sm:items-center justify-between gap-3 text-xs"
                  >
                    <div className="flex items-center gap-3">
                      <span className="font-mono font-bold px-2 py-0.5 rounded bg-linear-surface-3 text-linear-ink border border-linear-hairline">
                        Seq #{ev.sequence_id}
                      </span>
                      <div>
                        <div className="font-semibold text-linear-ink">{ev.delta_summary}</div>
                        <div className="text-[11px] text-linear-ink-muted mt-0.5">
                          Table: <span className="font-mono">{ev.table_name}</span> · Action: <span className="font-mono">{ev.action}</span> · Actor User ID: {ev.actor_user_id}
                        </div>
                      </div>
                    </div>

                    <div className="flex items-center gap-2 self-start sm:self-auto shrink-0">
                      <span className="text-[10px] uppercase font-bold px-2 py-0.5 rounded bg-rose-500/15 text-rose-400 border border-rose-500/30">
                        {ev.severity}
                      </span>
                      <span className="text-[11px] text-linear-ink-subtle">
                        {new Date(ev.created_at).toLocaleString()}
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Immutable Ledger Verification Notice */}
          <div className="p-4 rounded-xl bg-linear-surface-2 border border-linear-hairline text-xs text-linear-ink-subtle flex items-center justify-between gap-4">
            <div className="flex items-center gap-2.5">
              <ShieldCheck className="w-5 h-5 text-emerald-400 shrink-0" />
              <span>
                <strong>Cryptographic Integrity Guaranteed:</strong> The real PostgreSQL hash chain tail and audit log rows were not modified during this simulation. Replay runs in virtual read-only memory.
              </span>
            </div>
            <span className="text-[10px] font-mono text-linear-ink-muted shrink-0">
              Evaluated as of: {new Date(result.as_of).toLocaleTimeString()}
            </span>
          </div>
        </div>
      )}
    </div>
  );
}
