import { useState, useEffect } from 'react';
import { useSearchParams, Link } from 'react-router-dom';
import { useAuth } from '@clerk/clerk-react';
import { useQuery } from '@tanstack/react-query';
import {
  History,
  Search,
  CalendarClock,
  CheckCircle2,
  XCircle,
  Clock,
  GitCommit,
  ArrowRight,
  ExternalLink,
  Users,
} from 'lucide-react';
import {
  fetchTimeTravelState,
  fetchEmployees,
  fetchAuditLogs,
  AuditLogItem,
  EmployeeListItem,
} from '../../services/auditService';
import Button from '../common/Button';

export default function TimeTravelView() {
  const { getToken } = useAuth();
  const [searchParams, setSearchParams] = useSearchParams();

  const [employeeIdInput, setEmployeeIdInput] = useState('');
  const [dateInput, setDateInput] = useState('');
  const [timeInput, setTimeInput] = useState('');
  const [queryParams, setQueryParams] = useState<{ id: number; timestamp: string } | null>(null);

  // ── Fetch Employee Directory for the Dropdown Selector ─────────────────────
  const {
    data: employeeData,
    isLoading: isEmployeesLoading,
    isError: isEmployeesError,
  } = useQuery({
    queryKey: ['employeesDirectory'],
    queryFn: () => fetchEmployees(getToken, 100),
    staleTime: 60000,
  });

  const employees: EmployeeListItem[] = employeeData?.items || [];
  const parsedEmpId = parseInt(employeeIdInput, 10);
  const isValidEmpId = !isNaN(parsedEmpId) && parsedEmpId > 0;

  // ── Fetch Recent Audit Mutation Timeline for Selected Employee ─────────────
  const { data: employeeLogsData, isLoading: isLogsLoading } = useQuery({
    queryKey: ['employeeAuditLogs', parsedEmpId],
    queryFn: () => fetchAuditLogs({ employee_id: parsedEmpId, limit: 10 }, getToken),
    enabled: isValidEmpId,
    staleTime: 15000,
  });

  const employeeLogs: AuditLogItem[] = employeeLogsData?.items || [];

  // ── Parse URL Search Parameters on Mount / URL Changes ──────────────────────
  useEffect(() => {
    const urlEmpId = searchParams.get('emp_id');
    const urlAsOf = searchParams.get('as_of');

    if (urlEmpId) {
      setEmployeeIdInput(urlEmpId);
    }

    if (urlAsOf) {
      try {
        const d = new Date(urlAsOf);
        if (!isNaN(d.getTime())) {
          setDateInput(d.toISOString().split('T')[0]);
          const timePart = d.toISOString().split('T')[1];
          setTimeInput(timePart ? timePart.substring(0, 5) : '12:00');
        }
      } catch {
        // Ignore date parsing failure
      }
    }

    if (urlEmpId && urlAsOf) {
      const parsed = parseInt(urlEmpId, 10);
      if (!isNaN(parsed) && parsed > 0) {
        setQueryParams({ id: parsed, timestamp: urlAsOf });
      }
    }
  }, [searchParams]);

  // ── Time-Travel Query Execution ─────────────────────────────────────────────
  const { data: record, isLoading, isError, error } = useQuery({
    queryKey: ['timeTravel', queryParams?.id, queryParams?.timestamp],
    queryFn: async () => {
      if (!queryParams) return null;
      return fetchTimeTravelState(queryParams.id, queryParams.timestamp, getToken);
    },
    enabled: !!queryParams,
    retry: false,
    refetchInterval: false,
  });

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    if (!employeeIdInput || !dateInput || !timeInput) return;

    const timestamp = `${dateInput}T${timeInput}:00Z`;
    const id = parseInt(employeeIdInput, 10);
    setQueryParams({ id, timestamp });
    setSearchParams({ emp_id: String(id), as_of: timestamp });
  };

  const handleSelectEmployee = (idStr: string) => {
    setEmployeeIdInput(idStr);
    if (!idStr) return;
    const id = parseInt(idStr, 10);

    // Auto-populate date & time with current UTC if blank
    let curDate = dateInput;
    let curTime = timeInput;
    if (!curDate || !curTime) {
      const now = new Date();
      curDate = now.toISOString().split('T')[0];
      curTime = now.toISOString().split('T')[1].substring(0, 5);
      setDateInput(curDate);
      setTimeInput(curTime);
    }

    const timestamp = `${curDate}T${curTime}:00Z`;
    setQueryParams({ id, timestamp });
    setSearchParams({ emp_id: idStr, as_of: timestamp });
  };

  const handleSetToNow = () => {
    const now = new Date();
    const curDate = now.toISOString().split('T')[0];
    const curTime = now.toISOString().split('T')[1].substring(0, 5);
    setDateInput(curDate);
    setTimeInput(curTime);

    const id = parseInt(employeeIdInput, 10);
    if (!isNaN(id) && id > 0) {
      const timestamp = `${curDate}T${curTime}:00Z`;
      setQueryParams({ id, timestamp });
      setSearchParams({ emp_id: String(id), as_of: timestamp });
    }
  };

  const handleManualIdChange = (idStr: string) => {
    setEmployeeIdInput(idStr);
    if (!idStr) return;
    const id = parseInt(idStr, 10);
    if (!isNaN(id) && id > 0) {
      let curDate = dateInput;
      let curTime = timeInput;
      if (!curDate || !curTime) {
        const now = new Date();
        curDate = now.toISOString().split('T')[0];
        curTime = now.toISOString().split('T')[1].substring(0, 5);
        setDateInput(curDate);
        setTimeInput(curTime);
      }
      const timestamp = `${curDate}T${curTime}:00Z`;
      setQueryParams({ id, timestamp });
      setSearchParams({ emp_id: idStr, as_of: timestamp });
    }
  };

  const handleJumpToMutation = (createdAt: string) => {
    try {
      const d = new Date(createdAt);
      if (!isNaN(d.getTime())) {
        const dateStr = d.toISOString().split('T')[0];
        const timePart = d.toISOString().split('T')[1] || '12:00:00Z';
        const timeStr = timePart.substring(0, 5);
        setDateInput(dateStr);
        setTimeInput(timeStr);

        const id = parseInt(employeeIdInput, 10);
        if (!isNaN(id) && id > 0) {
          setQueryParams({ id, timestamp: createdAt });
          setSearchParams({ emp_id: String(id), as_of: createdAt });
        }
      }
    } catch {
      // Fallback
    }
  };

  const selectedEmployee = employees.find((e) => e.employee_id === parsedEmpId);

  return (
    <div className="space-y-6 animate-fade-cascade">
      {/* Header & Controls */}
      <div className="bg-linear-surface-1 border border-linear-hairline rounded-xl p-6 shadow-xs relative overflow-hidden">
        <div className="absolute top-0 right-0 p-8 opacity-5">
          <History className="w-32 h-32" />
        </div>

        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 mb-2">
          <h2 className="text-xl font-bold text-linear-ink flex items-center">
            <History className="w-5 h-5 mr-2 text-linear-primary" />
            Time-Travel State Reconstruction
          </h2>
          <span className="text-xs font-mono text-linear-primary bg-linear-primary/15 border border-linear-primary/30 px-3 py-1 rounded-md w-fit">
            O(log N) B-Tree Historical Walk
          </span>
        </div>

        <p className="text-sm text-linear-ink-muted mb-6 max-w-3xl">
          Deterministically reconstruct the exact state of any employee record at any past microsecond
          using PostgreSQL stored routine <code className="text-linear-primary font-mono text-xs">reconstruct_employee_state(:emp_id, :as_of)</code>.
          Select an employee below or choose a historical event directly from the mutation timeline.
        </p>

        <form onSubmit={handleSearch} className="space-y-4 max-w-4xl relative z-10">
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            
            {/* Employee Selector Dropdown */}
            <div>
              <label className="block text-xs font-medium text-linear-ink-muted mb-1 flex items-center justify-between">
                <span>Select Employee</span>
                {selectedEmployee && (
                  <span className="text-[11px] text-linear-success font-mono">
                    #{selectedEmployee.employee_id} {selectedEmployee.is_active ? 'Active' : 'Inactive'}
                  </span>
                )}
              </label>
              <div className="relative">
                <Users className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-linear-ink-subtle pointer-events-none" />
                <select
                  value={employeeIdInput}
                  onChange={(e) => handleSelectEmployee(e.target.value)}
                  disabled={isEmployeesLoading}
                  className="w-full bg-linear-canvas border border-linear-hairline rounded-xl py-2 pl-10 pr-8 text-sm text-linear-ink focus:outline-none focus:border-linear-primary focus:ring-1 focus:ring-linear-primary appearance-none cursor-pointer transition-colors duration-150 disabled:opacity-60"
                >
                  {isEmployeesLoading ? (
                    <option value="">Loading employee directory...</option>
                  ) : isEmployeesError ? (
                    <option value="">Error loading directory — enter ID manually</option>
                  ) : (
                    <>
                      <option value="">-- Choose Employee ({employees.length} available) --</option>
                      {employees.map((emp) => (
                        <option key={emp.employee_id} value={emp.employee_id}>
                          {emp.full_name} (#{emp.employee_id}) — {emp.role_title}
                        </option>
                      ))}
                    </>
                  )}
                </select>
                <div className="absolute right-3 top-1/2 -translate-y-1/2 pointer-events-none text-linear-ink-subtle text-xs">
                  ▼
                </div>
              </div>
            </div>

            {/* Target Date Input */}
            <div>
              <label className="block text-xs font-medium text-linear-ink-muted mb-1">Target Date (UTC)</label>
              <input
                type="date"
                required
                value={dateInput}
                onChange={(e) => setDateInput(e.target.value)}
                className="w-full bg-linear-canvas border border-linear-hairline rounded-xl py-2 px-4 text-sm text-linear-ink focus:outline-none focus:border-linear-primary focus:ring-1 focus:ring-linear-primary transition-colors duration-150 font-mono"
              />
            </div>

            {/* Target Time Input & Submit */}
            <div className="flex gap-2">
              <div className="flex-1">
                <div className="flex items-center justify-between mb-1">
                  <label className="block text-xs font-medium text-linear-ink-muted">Target Time (UTC)</label>
                  <Button
                    type="button"
                    variant="link"
                    size="xs"
                    portalTheme="auditor"
                    onClick={handleSetToNow}
                    title="Set target timestamp to current UTC"
                    className="text-[11px] text-linear-primary hover:text-linear-primary/80 font-mono"
                  >
                    Set to Now
                  </Button>
                </div>
                <input
                  type="time"
                  required
                  value={timeInput}
                  onChange={(e) => setTimeInput(e.target.value)}
                  className="w-full bg-linear-canvas border border-linear-hairline rounded-xl py-2 px-4 text-sm text-linear-ink focus:outline-none focus:border-linear-primary focus:ring-1 focus:ring-linear-primary transition-colors duration-150 font-mono"
                />
              </div>

              <div className="flex items-end">
                <Button
                  type="submit"
                  disabled={isLoading}
                  loading={isLoading}
                  variant="primary"
                  size="lg"
                  portalTheme="auditor"
                  leftIcon={<Search className="w-4 h-4" />}
                  className="h-[38px] px-5 rounded-xl font-medium"
                >
                  Reconstruct
                </Button>
              </div>
            </div>

          </div>

          {/* Quick manual ID override option */}
          <div className="flex items-center space-x-3 text-xs text-linear-ink-subtle">
            <span>Or enter ID manually:</span>
            <input
              type="number"
              min="1"
              placeholder="e.g. 13"
              value={employeeIdInput}
              onChange={(e) => handleManualIdChange(e.target.value)}
              className="w-20 bg-linear-canvas border border-linear-hairline rounded px-2 py-1 text-xs text-linear-ink font-mono focus:outline-none focus:border-linear-primary"
            />
            {selectedEmployee && (
              <span className="text-linear-ink-muted">
                Loaded: <strong className="text-linear-ink">{selectedEmployee.full_name}</strong> ({selectedEmployee.department_name})
              </span>
            )}
          </div>
        </form>
      </div>

      {/* Historical Audit Mutation Timeline for Selected Employee */}
      {isValidEmpId && (
        <div className="bg-linear-surface-1 border border-linear-hairline rounded-2xl p-5 shadow-sm">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 pb-3 mb-3 border-b border-linear-hairline">
            <div className="flex items-center space-x-2">
              <Clock className="w-4 h-4 text-linear-primary" />
              <h3 className="text-sm font-semibold text-linear-ink">
                Historical Mutation Timeline for Employee #{parsedEmpId}
              </h3>
              {selectedEmployee && (
                <span className="text-xs text-linear-ink-muted">({selectedEmployee.full_name})</span>
              )}
            </div>
            <span className="text-xs text-linear-ink-muted">
              Click any event below to auto-fill timestamp and reconstruct state
            </span>
          </div>

          {isLogsLoading ? (
            <div className="py-6 text-center text-xs text-linear-ink-muted">
              <div className="w-4 h-4 border-2 border-linear-primary/40 border-t-linear-primary rounded-full animate-fast-spin mx-auto mb-2" />
              Loading audit mutations...
            </div>
          ) : employeeLogs.length === 0 ? (
            <div className="py-4 text-center text-xs text-linear-ink-subtle">
              No audit log mutations recorded for Employee #{parsedEmpId}.
            </div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
              {employeeLogs.map((log) => {
                const isActionInsert = log.action === 'INSERT';
                const isActionDelete = log.action === 'DELETE';
                const actionBadgeClass = isActionInsert
                  ? 'bg-linear-success/15 text-linear-success border-linear-success/30'
                  : isActionDelete
                  ? 'bg-grafana-orange/15 text-grafana-orange border-grafana-orange/30'
                  : 'bg-amber-500/15 text-amber-400 border-amber-500/30';

                return (
                  <div
                    key={log.sequence_id}
                    onClick={() => handleJumpToMutation(log.created_at)}
                    role="button"
                    tabIndex={0}
                    onKeyDown={(e) => {
                      if (e.key === 'Enter' || e.key === ' ') {
                        e.preventDefault();
                        handleJumpToMutation(log.created_at);
                      }
                    }}
                    className="group bg-linear-canvas hover:bg-linear-surface-2 border border-linear-hairline hover:border-linear-hairline-strong rounded-xl p-3 transition-colors duration-150 cursor-pointer flex flex-col justify-between space-y-2 relative overflow-hidden focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-linear-primary"
                  >
                    <div className="flex items-center justify-between">
                      <div className="flex items-center space-x-2">
                        <span className={`text-[10px] font-mono font-bold px-2 py-0.5 rounded-md border ${actionBadgeClass}`}>
                          {log.action}
                        </span>
                        <span className="text-xs font-mono text-linear-ink-muted group-hover:text-linear-ink">
                          Seq #{log.sequence_id}
                        </span>
                      </div>
                      <span className="text-[10px] text-linear-ink-subtle font-mono">
                        {log.table_name}
                      </span>
                    </div>

                    <div className="text-xs text-linear-ink">
                      <span className="text-linear-ink-subtle block text-[10px]">Actor: {log.actor_name}</span>
                      <span className="text-[11px] text-linear-ink-muted font-mono">
                        {new Date(log.created_at).toLocaleString()}
                      </span>
                    </div>

                    <div className="pt-2 border-t border-linear-hairline flex items-center justify-between">
                      <span className="text-[11px] text-linear-primary flex items-center group-hover:underline">
                        Reconstruct as of this change
                        <ArrowRight className="w-3 h-3 ml-1 group-hover:translate-x-0.5 transition-transform duration-150" />
                      </span>
                      <div className="flex items-center space-x-2" onClick={(e) => e.stopPropagation()}>
                        <Link
                          to={`/auditor/chain?seq=${log.sequence_id}`}
                          title="Inspect in Chain Explorer"
                          className="text-linear-ink-subtle hover:text-linear-primary p-1 rounded transition-colors duration-150 focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-linear-primary"
                        >
                          <GitCommit className="w-3.5 h-3.5" />
                        </Link>
                        <Link
                          to={`/auditor/log?seq=${log.sequence_id}`}
                          title="View in Audit Log"
                          className="text-linear-ink-subtle hover:text-linear-primary p-1 rounded transition-colors duration-150 focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-linear-primary"
                        >
                          <ExternalLink className="w-3.5 h-3.5" />
                        </Link>
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      )}

      {/* Results Area */}
      {isError && (
        <div className="bg-grafana-orange/10 border border-grafana-orange/25 rounded-xl p-4 flex items-start text-grafana-orange animate-fade-cascade">
          <XCircle className="w-5 h-5 mr-3 mt-0.5 shrink-0" />
          <div>
            <h3 className="font-medium text-grafana-orange">Reconstruction Failed</h3>
            <p className="text-sm opacity-80 mt-1 text-grafana-orange/90">
              {error instanceof Error ? error.message : 'The requested record could not be reconstructed for the given timestamp.'}
            </p>
          </div>
        </div>
      )}

      {record && !isLoading && (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 animate-fade-cascade">
          {/* Formatted View */}
          <div className="lg:col-span-2 bg-linear-surface-1 border border-linear-hairline rounded-xl shadow-xs overflow-hidden">
            <div className="bg-linear-surface-2/40 px-6 py-4 border-b border-linear-hairline flex flex-col sm:flex-row sm:items-center justify-between gap-2">
              <h3 className="font-semibold text-linear-ink flex items-center">
                <CheckCircle2 className="w-4 h-4 mr-2 text-linear-success" />
                State Reconstructed Successfully
              </h3>
              <div className="flex items-center text-xs font-mono text-linear-primary bg-linear-primary/15 px-3 py-1 rounded-md border border-linear-primary/30">
                <CalendarClock className="w-3 h-3 mr-2" />
                AS OF {new Date(record.as_of).toLocaleString()}
              </div>
            </div>

            <div className="p-6">
              <div className="grid grid-cols-2 gap-x-12 gap-y-6">
                <div>
                  <div className="text-xs font-medium text-linear-ink-muted mb-1 uppercase tracking-wider">Employee ID</div>
                  <div className="text-lg font-mono text-linear-ink">#{record.employee_id}</div>
                </div>
                <div>
                  <div className="text-xs font-medium text-linear-ink-muted mb-1 uppercase tracking-wider">Status</div>
                  <div>
                    {record.is_active ? (
                      <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-linear-success/15 text-linear-success border border-linear-success/30">
                        Active
                      </span>
                    ) : (
                      <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-grafana-orange/15 text-grafana-orange border border-grafana-orange/30">
                        Inactive
                      </span>
                    )}
                  </div>
                </div>

                <div>
                  <div className="text-xs font-medium text-linear-ink-muted mb-1 uppercase tracking-wider">Full Name</div>
                  <div className="text-base text-linear-ink font-medium">{record.full_name}</div>
                </div>
                <div>
                  <div className="text-xs font-medium text-linear-ink-muted mb-1 uppercase tracking-wider">Email</div>
                  <div className="text-base text-linear-ink-muted">{record.email}</div>
                </div>

                <div>
                  <div className="text-xs font-medium text-linear-ink-muted mb-1 uppercase tracking-wider">Role & Dept</div>
                  <div className="text-base text-linear-ink">{record.role_title}</div>
                  <div className="text-sm text-linear-ink-muted">{record.department_name}</div>
                </div>
                <div>
                  <div className="text-xs font-medium text-linear-ink-muted mb-1 uppercase tracking-wider">Compensation</div>
                  <div className="text-base font-mono text-linear-ink">
                    {new Intl.NumberFormat('en-IN', { style: 'currency', currency: 'INR' }).format(record.salary)}
                  </div>
                </div>

                <div className="col-span-2">
                  <div className="text-xs font-medium text-linear-ink-muted mb-1 uppercase tracking-wider">Date Hired</div>
                  <div className="text-base text-linear-ink-muted">{new Date(record.date_hired).toLocaleDateString()}</div>
                </div>
              </div>
            </div>
          </div>

          {/* Raw JSON View */}
          <div className="bg-linear-canvas border border-linear-hairline rounded-2xl shadow-sm overflow-hidden flex flex-col">
            <div className="bg-linear-surface-1 px-4 py-3 border-b border-linear-hairline flex items-center justify-between">
              <span className="text-xs font-mono text-linear-ink-muted">reconstructed_state.json</span>
              <span className="text-[10px] uppercase font-bold tracking-wider px-2 py-0.5 rounded-md bg-linear-primary/15 text-linear-primary border border-linear-primary/30">
                O(log N) RECONSTRUCT
              </span>
            </div>
            <div className="p-4 flex-1 overflow-auto max-h-[350px]">
              <pre className="text-[11px] font-mono text-linear-ink-muted leading-relaxed">
                {JSON.stringify(record, null, 2)}
              </pre>
            </div>
          </div>
        </div>
      )}

      {!record && !isLoading && !isError && (
        <div className="h-44 border-2 border-dashed border-linear-hairline rounded-xl flex flex-col items-center justify-center text-linear-ink-subtle space-y-2">
          <History className="w-8 h-8 text-linear-ink-subtle/50" />
          <p className="text-sm">Select an employee and target time or choose an event from the mutation timeline above.</p>
        </div>
      )}
    </div>
  );
}
