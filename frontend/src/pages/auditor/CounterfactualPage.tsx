import React, { useState, useEffect, useMemo, useRef } from 'react';
import { useAuth } from '../../components/auth/AuthProvider';
import {
  GitCompare, Play, AlertCircle, ShieldCheck,
  DollarSign, Clock, Sparkles,
  RefreshCw, AlertTriangle, Search, ListChecks, X
} from 'lucide-react';
import {
  runCounterfactualSimulation,
  fetchAuditLogs,
  fetchEmployees,
  AuditLogItem,
  CounterfactualResult,
  EmployeeListItem,
} from '../../services/auditService';
import PageHeader from '../../components/common/PageHeader';
import { formatINR } from '../../lib/format';

const EVENTS_PER_PAGE = 50;

function describeEvent(event: AuditLogItem): string {
  const oldValue = event.forensic_before_value ?? event.old_value ?? {};
  const newValue = event.new_value ?? {};
  if (event.table_name === 'salary_history') {
    const oldAmount = oldValue.amount;
    const newAmount = newValue.amount;
    if (oldAmount !== undefined && newAmount !== undefined && Number.isFinite(Number(oldAmount)) && Number.isFinite(Number(newAmount))) {
      return `Amount ${formatINR(Number(oldAmount))} → ${formatINR(Number(newAmount))}`;
    }
    if (newAmount !== undefined && Number.isFinite(Number(newAmount))) {
      const effectiveDate = newValue.effective_date ? ` · effective ${String(newValue.effective_date)}` : '';
      return `Salary recorded: ${formatINR(Number(newAmount))}${effectiveDate}`;
    }
  }

  const safeFields = ['role_id', 'department_id', 'is_active'];
  const changes = safeFields
    .filter((field) => field in newValue && oldValue[field] !== newValue[field])
    .map((field) => `${field.replace(/_/g, ' ')}: ${String(oldValue[field] ?? '—')} → ${String(newValue[field])}`);
  return changes.length > 0 ? changes.join(' · ') : `${event.action} ${event.table_name} row #${event.row_id}`;
}

export default function CounterfactualPage() {
  const { getToken } = useAuth();

  // Inputs
  const [employeeId, setEmployeeId] = useState<number>(1);
  const [manualEmployeeId, setManualEmployeeId] = useState('');
  const [selectedSequenceIds, setSelectedSequenceIds] = useState<number[]>([]);
  const [asOfInput, setAsOfInput] = useState<string>('');
  const [revealPii, setRevealPii] = useState(false);
  const [eventSearch, setEventSearch] = useState('');
  
  // State
  const [employees, setEmployees] = useState<EmployeeListItem[]>([]);
  const [employeeEvents, setEmployeeEvents] = useState<AuditLogItem[]>([]);
  const [eventPage, setEventPage] = useState(1);
  const [eventPages, setEventPages] = useState(0);
  const [eventTotal, setEventTotal] = useState(0);
  const [isLoadingEvents, setIsLoadingEvents] = useState(false);
  const [eventError, setEventError] = useState<string | null>(null);
  const [isSimulating, setIsSimulating] = useState(false);
  const [result, setResult] = useState<CounterfactualResult | null>(null);
  const simulationRequestId = useRef(0);
  const [error, setError] = useState<string | null>(null);

  // Fetch initial employee directory for easy selection
  useEffect(() => {
    let isMounted = true;
    async function loadDirectory() {
      try {
        const data = await fetchEmployees(getToken, 100);
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

  // Load the selected employee's real audit events so users can choose rows
  // directly instead of searching Audit Log and copying sequence numbers.
  useEffect(() => {
    let isMounted = true;
    simulationRequestId.current += 1;
    setIsSimulating(false);
    setEmployeeEvents([]);
    setSelectedSequenceIds([]);
    setEventPage(1);
    setEventSearch('');
    setResult(null);
    setEventError(null);
    setIsLoadingEvents(true);

    fetchAuditLogs({ employee_id: employeeId, page: 1, limit: EVENTS_PER_PAGE }, getToken)
      .then((data) => {
        if (!isMounted) return;
        setEmployeeEvents(data.items);
        setEventPages(data.pages);
        setEventTotal(data.total);
      })
      .catch((err: unknown) => {
        if (!isMounted) return;
        setEventError(err instanceof Error ? err.message : 'Could not load this employee’s audit events.');
      })
      .finally(() => {
        if (isMounted) setIsLoadingEvents(false);
      });

    return () => { isMounted = false; };
  }, [employeeId, getToken]);

  const visibleEvents = useMemo(() => {
    const query = eventSearch.trim().toLowerCase();
    if (!query) return employeeEvents;
    return employeeEvents.filter((event) =>
      [
        String(event.sequence_id),
        event.action,
        event.table_name,
        String(event.row_id),
        describeEvent(event),
      ].some((value) => value.toLowerCase().includes(query)),
    );
  }, [employeeEvents, eventSearch]);

  const actualSalary = Number(result?.actual_state?.salary ?? result?.blast_radius.salary_actual ?? 0);
  const replaySalary = Number(result?.counterfactual_state?.salary ?? result?.blast_radius.salary_counterfactual ?? 0);
  const salaryVariance = actualSalary - replaySalary;
  const salaryVarianceAmount = Math.abs(salaryVariance);

  const loadEarlierEvents = async () => {
    const nextPage = eventPage + 1;
    setIsLoadingEvents(true);
    setEventError(null);
    try {
      const data = await fetchAuditLogs(
        { employee_id: employeeId, page: nextPage, limit: EVENTS_PER_PAGE },
        getToken,
      );
      setEmployeeEvents((current) => [...current, ...data.items]);
      setEventPage(nextPage);
      setEventPages(data.pages);
      setEventTotal(data.total);
    } catch (err: unknown) {
      setEventError(err instanceof Error ? err.message : 'Could not load earlier audit events.');
    } finally {
      setIsLoadingEvents(false);
    }
  };

  const toggleSequence = (sequenceId: number) => {
    simulationRequestId.current += 1;
    setSelectedSequenceIds((current) => current.includes(sequenceId)
      ? current.filter((id) => id !== sequenceId)
      : [...current, sequenceId].sort((a, b) => a - b));
    setResult(null);
  };

  const handleRunSimulation = async (e?: React.FormEvent) => {
    if (e) e.preventDefault();
    setError(null);

    if (selectedSequenceIds.length === 0) {
      setError('Choose at least one event from this employee’s audit history.');
      return;
    }
    if (!revealPii) {
      setError('Confirm the recorded reveal of employee and salary details before running the replay.');
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
    const requestId = ++simulationRequestId.current;
    try {
      const res = await runCounterfactualSimulation(
        {
          employee_id: Number(employeeId),
          skip_sequence_ids: selectedSequenceIds,
          as_of: formattedAsOf,
          include_pii: true,
        },
        getToken,
      );
      if (requestId === simulationRequestId.current) setResult(res);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err);
      if (requestId === simulationRequestId.current) setError(msg || 'Simulation failed. Check sequence IDs and employee ID.');
    } finally {
      if (requestId === simulationRequestId.current) setIsSimulating(false);
    }
  };

  return (
    <div className="space-y-6 max-w-7xl mx-auto pb-12">
      <PageHeader
        icon={<GitCompare className="h-5 w-5" />}
        title={'Counterfactual "What-If" Provenance Replay'}
        description="Simulate alternative outcomes while leaving the tamper-evident audit chain unchanged."
        action={
          <>
          <span className="text-[11px] font-semibold px-2.5 py-1 rounded-full bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 flex items-center gap-1.5">
            <Sparkles className="w-3.5 h-3.5" />
            Event-Exclusion Replay
          </span>
          <span className="text-[11px] font-semibold px-2.5 py-1 rounded-full bg-linear-surface-2 text-linear-ink-subtle border border-linear-hairline flex items-center gap-1.5">
            <ShieldCheck className="w-3.5 h-3.5 text-linear-primary" />
            Read-Only Replay
          </span>
          </>
        }
      />

      {/* Control Panel Card */}
      <div className="bg-linear-surface-1 border border-linear-hairline rounded-xl p-5 shadow-xs">
        <form onSubmit={handleRunSimulation} className="space-y-4">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {/* Employee Selector */}
            <div>
              <label htmlFor="counterfactual-personnel" className="block text-xs font-semibold text-linear-ink-subtle uppercase tracking-wider mb-1.5">
                Target Personnel
              </label>
              {employees.length > 0 && (
                <select
                  id="counterfactual-personnel"
                  value={employeeId}
                  onChange={(e) => setEmployeeId(Number(e.target.value))}
                  className="w-full text-sm bg-linear-surface-2 border border-linear-hairline rounded-lg px-3 py-2 text-linear-ink focus:outline-hidden focus:border-linear-primary"
                >
                  {!employees.some((emp) => emp.employee_id === employeeId) && <option value={employeeId}>Employee #{employeeId} — selected by ID</option>}
                  {employees.map((emp) => (
                    <option key={emp.employee_id} value={emp.employee_id}>
                      #{emp.employee_id} — {emp.full_name} ({emp.role_title || 'Employee'})
                    </option>
                  ))}
                </select>
              )}
              <div className="mt-3 flex flex-wrap items-end gap-2">
                <label className="grow text-xs text-linear-ink-muted">Employee ID
                <input
                  type="number"
                  min="1" step="1"
                  value={manualEmployeeId}
                  onChange={(e) => setManualEmployeeId(e.target.value)}
                  placeholder="Employee ID (e.g. 42)"
                  className="w-full text-sm bg-linear-surface-2 border border-linear-hairline rounded-lg px-3 py-2 text-linear-ink focus:outline-hidden focus:border-linear-primary"
                />
                </label>
                <button type="button" className="rounded-lg border border-linear-hairline px-3 py-2 text-xs text-linear-ink disabled:opacity-40"
                  disabled={!Number.isSafeInteger(Number(manualEmployeeId)) || Number(manualEmployeeId) <= 0}
                  onClick={() => setEmployeeId(Number(manualEmployeeId))}>Use employee ID</button>
              </div>
              <p className="mt-2 text-xs text-linear-ink-muted">The quick list shows the first 100 employees. Enter any employee ID to investigate records outside that list.</p>
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

          {/* Employee-specific event picker */}
          <section className="overflow-hidden rounded-lg border border-linear-hairline" aria-labelledby="counterfactual-event-picker-title">
            <div className="flex flex-wrap items-center justify-between gap-3 border-b border-linear-hairline bg-linear-surface-2/70 px-3 py-2.5">
              <div>
                <h3 id="counterfactual-event-picker-title" className="flex items-center gap-2 text-xs font-bold uppercase tracking-wide text-linear-ink">
                  <ListChecks className="h-3.5 w-3.5 text-linear-primary" />
                  Choose events to exclude
                </h3>
                <p className="mt-0.5 text-[11px] text-linear-ink-muted">
                  {selectedSequenceIds.length} selected · showing {employeeEvents.length} of {eventTotal} events for Employee #{employeeId}
                </p>
              </div>
              <div className="flex items-center gap-2">
                <label className="relative">
                  <Search className="pointer-events-none absolute left-2 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-linear-ink-muted" />
                  <input
                    type="search"
                    value={eventSearch}
                    onChange={(e) => setEventSearch(e.target.value)}
                    placeholder="Find event"
                    className="w-44 rounded-md border border-linear-hairline bg-linear-canvas py-1.5 pl-7 pr-2 text-xs text-linear-ink placeholder:text-linear-ink-muted focus:border-linear-primary focus:outline-hidden"
                  />
                </label>
                {selectedSequenceIds.length > 0 && (
                  <button
                    type="button"
                    onClick={() => { setSelectedSequenceIds([]); setResult(null); }}
                    className="inline-flex items-center gap-1 rounded-md px-2 py-1.5 text-[11px] text-linear-ink-muted hover:bg-linear-canvas hover:text-linear-ink"
                  >
                    <X className="h-3 w-3" /> Clear
                  </button>
                )}
              </div>
            </div>

            {eventError && (
              <p role="alert" className="border-b border-status-danger/20 bg-status-danger/5 px-3 py-2 text-xs text-status-danger">{eventError}</p>
            )}

            <div className="max-h-72 overflow-auto">
              {isLoadingEvents && employeeEvents.length === 0 ? (
                <p className="px-3 py-8 text-center text-xs text-linear-ink-muted">Loading this employee’s audit events…</p>
              ) : visibleEvents.length === 0 ? (
                <p className="px-3 py-8 text-center text-xs text-linear-ink-muted">
                  {employeeEvents.length === 0 ? 'No audit events are available for this employee.' : 'No events match your search.'}
                </p>
              ) : (
                <table className="w-full min-w-[720px] text-left text-xs">
                  <thead className="sticky top-0 z-10 bg-linear-surface-1 text-[10px] font-semibold uppercase tracking-wide text-linear-ink-muted">
                    <tr>
                      <th className="w-9 px-3 py-2"><span className="sr-only">Select</span></th>
                      <th className="px-2 py-2">Sequence</th>
                      <th className="px-2 py-2">Event</th>
                      <th className="px-2 py-2">Change</th>
                      <th className="px-2 py-2">Recorded</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-linear-hairline/70">
                    {visibleEvents.map((event) => {
                      const isSelected = selectedSequenceIds.includes(event.sequence_id);
                      return (
                        <tr
                          key={event.sequence_id}
                          className={isSelected ? 'bg-linear-primary/10' : 'hover:bg-linear-surface-2/60'}
                        >
                          <td className="px-3 py-2">
                            <input
                              type="checkbox"
                              checked={isSelected}
                              onChange={() => toggleSequence(event.sequence_id)}
                              aria-label={`Exclude sequence ${event.sequence_id}`}
                              className="h-4 w-4 accent-linear-primary"
                            />
                          </td>
                          <td className="px-2 py-2 font-mono font-bold text-linear-primary">#{event.sequence_id}</td>
                          <td className="px-2 py-2">
                            <div className="flex flex-wrap items-center gap-1.5">
                            <span className="font-semibold text-linear-ink">{event.action}</span>
                            <span className="font-mono text-linear-ink-muted">{event.table_name} · row #{event.row_id}</span>
                            </div>
                          </td>
                          <td className="max-w-[360px] truncate px-2 py-2 text-linear-ink-subtle" title={describeEvent(event)}>{describeEvent(event)}</td>
                          <td className="whitespace-nowrap px-2 py-2 text-linear-ink-muted" title={new Date(event.created_at).toLocaleString()}>{new Date(event.created_at).toLocaleString()}</td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              )}
            </div>

            {eventPage < eventPages && (
              <div className="border-t border-linear-hairline px-3 py-2 text-center">
                <button
                  type="button"
                  onClick={loadEarlierEvents}
                  disabled={isLoadingEvents}
                  className="text-xs font-semibold text-linear-primary hover:underline disabled:opacity-50"
                >
                  {isLoadingEvents ? 'Loading…' : 'Load earlier events'}
                </button>
              </div>
            )}
          </section>

          {/* Guidance & Action */}
          <label className="flex items-start gap-2 text-xs text-linear-ink-muted">
            <input type="checkbox" checked={revealPii} onChange={(event) => { simulationRequestId.current += 1; setRevealPii(event.target.checked); setResult(null); setIsSimulating(false); }} />
            Reveal employee and salary details in the replay. This access is recorded.
          </label>
          <div className="flex flex-wrap items-center justify-between gap-3 pt-2 border-t border-linear-hairline/60">
            <p className="text-xs text-linear-ink-muted">
              Select one or more events above. The replay excludes them in memory and leaves the ledger unchanged.
            </p>

            <button
              type="submit"
              disabled={isSimulating || isLoadingEvents || selectedSequenceIds.length === 0 || !revealPii}
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
      {result && revealPii && (
        <div className="space-y-6">
          {/* Blast Radius Impact Cards */}
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
            <div className="bg-linear-surface-1 border border-linear-hairline rounded-xl p-4 shadow-xs">
              <div className="flex items-center justify-between text-xs text-linear-ink-subtle mb-1">
                <span>Annual Salary Variance (Actual − Replay)</span>
                <GitCompare className="w-4 h-4 text-amber-400" />
              </div>
              <div className="text-2xl font-bold text-amber-400 tracking-tight">
                {salaryVariance > 0 ? '+' : salaryVariance < 0 ? '−' : ''}{formatINR(salaryVarianceAmount, true)}
              </div>
              <p className="text-[11px] text-linear-ink-muted mt-1">
                {salaryVariance > 0
                  ? `Actual salary is higher by ${formatINR(salaryVarianceAmount)} per year`
                  : salaryVariance < 0
                    ? `Replay salary is higher by ${formatINR(salaryVarianceAmount)} per year`
                    : 'Actual and replay salary rates match'}
              </p>
            </div>

            <div className="bg-linear-surface-1 border border-linear-hairline rounded-xl p-4 shadow-xs">
              <div className="flex items-center justify-between text-xs text-linear-ink-subtle mb-1">
                <span>Estimated Cumulative Overpayment</span>
                <DollarSign className="w-4 h-4 text-rose-400" />
              </div>
              <div className="text-2xl font-bold text-rose-400 tracking-tight">
                {formatINR(result.blast_radius.salary_overpaid_cumulative, true)}
              </div>
              <p className="text-[11px] text-linear-ink-muted mt-1">
                Counts only periods when actual salary exceeds replay; not a payroll payment total
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
                      {formatINR(actualSalary, true)}
                    </td>
                    <td className="py-3 px-4 font-mono font-semibold text-emerald-400">
                      {formatINR(replaySalary, true)}
                    </td>
                    <td className="py-3 px-4">
                      {salaryVariance > 0 ? (
                        <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-semibold bg-rose-500/20 text-rose-300 border border-rose-500/30">
                          Actual higher by {formatINR(salaryVarianceAmount)} / yr
                        </span>
                      ) : salaryVariance < 0 ? (
                        <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-semibold bg-amber-500/20 text-amber-300 border border-amber-500/30">
                          Replay higher by {formatINR(salaryVarianceAmount)} / yr
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
                <strong>Read-Only Replay:</strong> The simulation leaves audit rows unchanged. Run chain verification separately to check their integrity. The exposure estimate is based on annual salary rates and effective dates, not payroll payments.
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
