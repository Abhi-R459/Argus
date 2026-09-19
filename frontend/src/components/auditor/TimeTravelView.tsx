import { useState, useEffect, useRef } from 'react';
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
  X,
} from 'lucide-react';
import {
  fetchTimeTravelState,
  fetchEmployees,
  fetchAuditLogs,
  AuditLogItem,
  EmployeeListItem,
} from '../../services/auditService';
import Button from '../common/Button';
import { formatINR } from '../../lib/format';
import { getActionSemantic } from '../../lib/semantics';
import { EmptyState } from '../common/EmptyState';

export default function TimeTravelView() {
  const { getToken } = useAuth();
  const [searchParams, setSearchParams] = useSearchParams();

  const [employeeIdInput, setEmployeeIdInput] = useState('');
  const [dateInput, setDateInput] = useState('');
  const [timeInput, setTimeInput] = useState('');
  const [queryParams, setQueryParams] = useState<{ id: number; timestamp: string } | null>(null);

  // ── Autocomplete Search State ───────────────────────────────────────────────
  const [searchQuery, setSearchQuery] = useState('');
  const [debouncedSearchQuery, setDebouncedSearchQuery] = useState('');
  const [isDropdownOpen, setIsDropdownOpen] = useState(false);
  const [activeOptionIndex, setActiveOptionIndex] = useState<number>(-1);
  const searchContainerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const handler = setTimeout(() => {
      setDebouncedSearchQuery(searchQuery);
    }, 250);
    return () => clearTimeout(handler);
  }, [searchQuery]);

  useEffect(() => {
    setActiveOptionIndex(-1);
  }, [debouncedSearchQuery, isDropdownOpen]);

  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (searchContainerRef.current && !searchContainerRef.current.contains(event.target as Node)) {
        setIsDropdownOpen(false);
      }
    }
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const parsedEmpId = parseInt(employeeIdInput, 10);
  const isValidEmpId = !isNaN(parsedEmpId) && parsedEmpId > 0;

  // ── Live Autocomplete Employee Search (Scales to 10,000s) ───────────────────
  const {
    data: searchResultsData,
    isLoading: isSearchLoading,
  } = useQuery({
    queryKey: ['employeesSearch', debouncedSearchQuery],
    queryFn: () => fetchEmployees(getToken, 10, debouncedSearchQuery || undefined),
    enabled: isDropdownOpen,
    staleTime: 30000,
  });

  const searchResults: EmployeeListItem[] = searchResultsData?.items || [];

  // ── Fetch Targeted Details for Currently Selected Employee ───────────────────
  const { data: selectedEmpData } = useQuery({
    queryKey: ['employeeDetail', parsedEmpId],
    queryFn: () => fetchEmployees(getToken, 1, String(parsedEmpId)),
    enabled: isValidEmpId,
    staleTime: 60000,
  });

  const selectedEmployee: EmployeeListItem | undefined =
    selectedEmpData?.items?.find((e) => e.employee_id === parsedEmpId) ||
    searchResults.find((e) => e.employee_id === parsedEmpId);

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


  return (
    <div className="space-y-6 animate-fade-cascade">
      {/* Header & Controls */}
      <div className="bg-linear-surface-1 border border-linear-hairline rounded-2xl p-6 shadow-xs relative overflow-hidden">
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

        <form onSubmit={handleSearch} className="space-y-4 max-w-5xl relative z-10">
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-12 gap-4 items-end">
            
            {/* Employee Selector Autocomplete Combobox */}
            <div ref={searchContainerRef} className="sm:col-span-2 lg:col-span-5 relative">
              <div className="flex items-center justify-between h-5 mb-1.5">
                <label className="block text-xs font-medium text-linear-ink-muted">Select Employee</label>
                {selectedEmployee && (
                  <span className={`text-[11px] font-mono ${selectedEmployee.is_active ? 'text-emerald-400' : 'text-amber-400'}`}>
                    #{selectedEmployee.employee_id} {selectedEmployee.is_active ? 'Active' : 'Inactive'}
                  </span>
                )}
              </div>

              {isValidEmpId && !isDropdownOpen ? (
                <div className="w-full bg-linear-canvas border border-linear-hairline hover:border-linear-primary/50 rounded-xl p-2 px-3 flex items-center justify-between transition-colors min-h-[42px]">
                  <div className="flex items-center gap-2.5 min-w-0">
                    <div className="w-7 h-7 rounded-lg bg-linear-primary/10 border border-linear-primary/30 flex items-center justify-center text-linear-primary font-bold text-xs shrink-0">
                      {selectedEmployee ? selectedEmployee.full_name.split(' ').map((n) => n[0]).join('').slice(0, 2) : `#${parsedEmpId}`}
                    </div>
                    <div className="min-w-0">
                      <div className="flex items-center gap-1.5">
                        <span className="font-semibold text-xs text-linear-ink truncate">
                          {selectedEmployee ? selectedEmployee.full_name : `Employee #${parsedEmpId}`}
                        </span>
                        <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-linear-surface-2 text-linear-ink-muted shrink-0">
                          #EMP-{String(parsedEmpId).padStart(4, '0')}
                        </span>
                      </div>
                      {selectedEmployee && (
                        <p className="text-[11px] text-linear-ink-muted truncate">
                          {selectedEmployee.role_title} · {selectedEmployee.department_name}
                        </p>
                      )}
                    </div>
                  </div>
                  <button
                    type="button"
                    onClick={() => {
                      setIsDropdownOpen(true);
                      setSearchQuery('');
                    }}
                    className="ml-2 text-xs text-linear-primary hover:text-linear-primary-hover font-medium px-2 py-1 rounded-md hover:bg-linear-primary/10 transition-colors shrink-0"
                  >
                    Change
                  </button>
                </div>
              ) : (
                <div className="relative">
                  <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-linear-ink-subtle pointer-events-none" />
                  <input
                    type="text"
                    role="combobox"
                    aria-expanded={isDropdownOpen}
                    aria-autocomplete="list"
                    aria-controls="employee-search-listbox"
                    aria-activedescendant={
                      activeOptionIndex >= 0 && searchResults[activeOptionIndex]
                        ? `employee-option-${searchResults[activeOptionIndex].employee_id}`
                        : undefined
                    }
                    value={searchQuery}
                    onChange={(e) => {
                      setSearchQuery(e.target.value);
                      if (!isDropdownOpen) setIsDropdownOpen(true);
                    }}
                    onFocus={() => setIsDropdownOpen(true)}
                    onKeyDown={(e) => {
                      if (e.key === 'Escape') {
                        setIsDropdownOpen(false);
                        setActiveOptionIndex(-1);
                      } else if (e.key === 'ArrowDown') {
                        e.preventDefault();
                        if (!isDropdownOpen) {
                          setIsDropdownOpen(true);
                        } else if (searchResults.length > 0) {
                          setActiveOptionIndex((prev) => (prev < searchResults.length - 1 ? prev + 1 : 0));
                        }
                      } else if (e.key === 'ArrowUp') {
                        e.preventDefault();
                        if (isDropdownOpen && searchResults.length > 0) {
                          setActiveOptionIndex((prev) => (prev > 0 ? prev - 1 : searchResults.length - 1));
                        }
                      } else if (e.key === 'Enter') {
                        if (isDropdownOpen && activeOptionIndex >= 0 && activeOptionIndex < searchResults.length) {
                          e.preventDefault();
                          handleSelectEmployee(String(searchResults[activeOptionIndex].employee_id));
                          setIsDropdownOpen(false);
                          setSearchQuery('');
                        }
                      }
                    }}
                    placeholder="Search name, email, or #ID (e.g. Marcus, #1)..."
                    className="w-full bg-linear-canvas border border-linear-hairline focus:border-linear-primary rounded-xl py-2 pl-9 pr-8 text-sm text-linear-ink focus:outline-none focus:ring-1 focus:ring-linear-primary transition-colors h-[42px]"
                    autoFocus={isDropdownOpen && isValidEmpId}
                  />
                  {searchQuery ? (
                    <button
                      type="button"
                      onClick={() => setSearchQuery('')}
                      className="absolute right-2.5 top-1/2 -translate-y-1/2 text-linear-ink-subtle hover:text-linear-ink p-1 rounded"
                    >
                      <X className="w-3.5 h-3.5" />
                    </button>
                  ) : isValidEmpId && (
                    <button
                      type="button"
                      onClick={() => setIsDropdownOpen(false)}
                      className="absolute right-2.5 top-1/2 -translate-y-1/2 text-xs text-linear-ink-muted hover:text-linear-ink px-1"
                    >
                      Cancel
                    </button>
                  )}
                </div>
              )}

              {/* Floating Match Dropdown */}
              {isDropdownOpen && (
                <div
                  id="employee-search-listbox"
                  role="listbox"
                  aria-label="Matching Personnel"
                  className="absolute left-0 right-0 top-full mt-1.5 z-50 bg-linear-surface-1 border border-linear-hairline rounded-xl shadow-xl overflow-hidden max-h-72 overflow-y-auto"
                >
                  {isSearchLoading ? (
                    <div className="p-4 text-center text-xs text-linear-ink-muted flex items-center justify-center gap-2">
                      <div className="w-3.5 h-3.5 border-2 border-linear-primary border-t-transparent rounded-full animate-spin" />
                      Searching workforce directory...
                    </div>
                  ) : searchResults.length === 0 ? (
                    <div className="p-4 text-center text-xs text-linear-ink-muted">
                      No employees found matching <strong className="text-linear-ink font-mono">"{debouncedSearchQuery || '...'}"</strong>
                    </div>
                  ) : (
                    <div className="py-1 divide-y divide-linear-hairline/40">
                      <div className="px-3 py-1.5 text-[10px] font-mono text-linear-ink-subtle uppercase tracking-wider bg-linear-surface-2/50 flex justify-between">
                        <span>Matching Personnel ({searchResults.length})</span>
                        <span>Use ↑↓ keys, Enter to select, ESC to close</span>
                      </div>
                      {searchResults.map((emp, idx) => (
                        <div
                          key={emp.employee_id}
                          id={`employee-option-${emp.employee_id}`}
                          role="option"
                          aria-selected={idx === activeOptionIndex}
                          onClick={() => {
                            handleSelectEmployee(String(emp.employee_id));
                            setIsDropdownOpen(false);
                            setSearchQuery('');
                          }}
                          className={`p-2.5 px-3 cursor-pointer flex items-center justify-between group transition-colors ${
                            idx === activeOptionIndex
                              ? 'bg-linear-surface-2 ring-1 ring-inset ring-linear-primary/40'
                              : 'hover:bg-linear-surface-2'
                          }`}
                        >
                          <div className="flex items-center gap-2.5 min-w-0">
                            <div className="w-6 h-6 rounded-md bg-linear-primary/10 border border-linear-primary/20 flex items-center justify-center text-linear-primary text-[10px] font-bold shrink-0">
                              {emp.full_name.split(' ').map((n) => n[0]).join('').slice(0, 2)}
                            </div>
                            <div className="min-w-0">
                              <div className="flex items-center gap-1.5">
                                <span className="text-xs font-semibold text-linear-ink group-hover:text-linear-primary truncate transition-colors">
                                  {emp.full_name}
                                </span>
                                <span className="text-[10px] font-mono text-linear-ink-muted">
                                  #{emp.employee_id}
                                </span>
                              </div>
                              <p className="text-[11px] text-linear-ink-muted truncate">
                                {emp.role_title} · {emp.department_name}
                              </p>
                            </div>
                          </div>
                          <div className="flex items-center gap-2 shrink-0 ml-2">
                            <span className={`text-[10px] px-1.5 py-0.5 rounded font-medium ${
                              emp.is_active ? 'bg-emerald-500/10 text-emerald-400' : 'bg-rose-500/10 text-rose-400'
                            }`}>
                              {emp.is_active ? 'Active' : 'Inactive'}
                            </span>
                            <ArrowRight className="w-3.5 h-3.5 text-linear-ink-subtle group-hover:text-linear-primary transition-transform group-hover:translate-x-0.5" />
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              )}
            </div>

            {/* Target Date Input */}
            <div className="lg:col-span-3">
              <div className="flex items-center h-5 mb-1.5">
                <label className="block text-xs font-medium text-linear-ink-muted">Target Date (UTC)</label>
              </div>
              <input
                type="date"
                required
                value={dateInput}
                onChange={(e) => setDateInput(e.target.value)}
                className="w-full bg-linear-canvas border border-linear-hairline rounded-xl py-2 px-3 text-xs text-linear-ink focus:outline-none focus:border-linear-primary focus:ring-1 focus:ring-linear-primary transition-colors duration-150 font-mono h-[42px]"
              />
            </div>

            {/* Target Time Input with Set to Now */}
            <div className="lg:col-span-2">
              <div className="flex items-center justify-between h-5 mb-1.5">
                <label className="block text-xs font-medium text-linear-ink-muted">Time (UTC)</label>
                <button
                  type="button"
                  onClick={handleSetToNow}
                  title="Set target timestamp to current UTC"
                  className="text-[11px] text-linear-primary hover:text-linear-primary-hover font-mono hover:underline focus-visible:outline-none"
                >
                  Set Now
                </button>
              </div>
              <input
                type="time"
                required
                value={timeInput}
                onChange={(e) => setTimeInput(e.target.value)}
                className="w-full bg-linear-canvas border border-linear-hairline rounded-xl py-2 px-3 text-xs text-linear-ink focus:outline-none focus:border-linear-primary focus:ring-1 focus:ring-linear-primary transition-colors duration-150 font-mono h-[42px]"
              />
            </div>

            {/* Submit Button */}
            <div className="sm:col-span-2 lg:col-span-2">
              <div className="h-5 mb-1.5 hidden lg:block" />
              <Button
                type="submit"
                disabled={isLoading}
                loading={isLoading}
                variant="primary"
                size="md"
                portalTheme="auditor"
                leftIcon={<Search className="w-3.5 h-3.5" />}
                className="w-full h-[42px] rounded-xl font-medium text-xs"
              >
                Reconstruct
              </Button>
            </div>

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
              {employeeLogs.map((log) => (
                <div
                  key={log.sequence_id}
                  className="bg-linear-canvas hover:bg-linear-surface-2/70 border border-linear-hairline hover:border-linear-hairline-strong rounded-xl p-3.5 transition-colors duration-150 flex flex-col justify-between space-y-3 relative overflow-hidden"
                >
                  <div className="flex items-center justify-between">
                    <div className="flex items-center space-x-2">
                      <span className={`text-[10px] font-mono font-bold px-2 py-0.5 rounded-md border ${
                        getActionSemantic(log.action, log.table_name, 'auditor').className
                      }`}>
                        {log.action}
                      </span>
                      <span className="text-xs font-mono text-linear-ink-muted">
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

                  <div className="pt-2 border-t border-linear-hairline flex items-center justify-between gap-2">
                    <button
                      type="button"
                      onClick={() => handleJumpToMutation(log.created_at)}
                      className="text-[11px] text-linear-primary hover:text-linear-primary-hover font-medium flex items-center group cursor-pointer focus-visible:outline-none focus-visible:underline text-left"
                    >
                      <span>Reconstruct as of this change</span>
                      <ArrowRight className="w-3 h-3 ml-1 group-hover:translate-x-0.5 transition-transform duration-150" />
                    </button>
                    <div className="flex items-center space-x-1 shrink-0">
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
              ))}
            </div>
          )}
        </div>
      )}

      {/* Results Area */}
      {isError && (
        <div className="bg-grafana-orange/10 border border-grafana-orange/25 rounded-2xl p-4 flex items-start text-grafana-orange animate-fade-cascade">
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
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 animate-fade-cascade items-stretch">
          {/* Formatted View */}
          <div className="lg:col-span-2 bg-linear-surface-1 border border-linear-hairline rounded-2xl shadow-xs overflow-hidden flex flex-col justify-between">
            <div>
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
                      {formatINR(record.salary)}
                    </div>
                  </div>

                  <div className="col-span-2">
                    <div className="text-xs font-medium text-linear-ink-muted mb-1 uppercase tracking-wider">Date Hired</div>
                    <div className="text-base text-linear-ink-muted">{record.date_hired}</div>
                  </div>
                </div>
              </div>
            </div>
          </div>

          {/* Raw JSON View */}
          <div className="bg-linear-canvas border border-linear-hairline rounded-2xl shadow-xs overflow-hidden flex flex-col">
            <div className="bg-linear-surface-1 px-4 py-3 border-b border-linear-hairline flex items-center justify-between">
              <span className="text-xs font-mono text-linear-ink-muted">reconstructed_state.json</span>
              <span className="text-[10px] uppercase font-bold tracking-wider px-2 py-0.5 rounded-md bg-linear-primary/15 text-linear-primary border border-linear-primary/30">
                O(log N) RECONSTRUCT
              </span>
            </div>
            <div className="p-4 flex-1 overflow-auto max-h-[380px]">
              <pre className="text-[11px] font-mono text-linear-ink-muted leading-relaxed">
                {JSON.stringify(record, null, 2)}
              </pre>
            </div>
          </div>
        </div>
      )}

      {!record && !isLoading && !isError && (
        <EmptyState
          icon={<History className="w-6 h-6 text-linear-primary" />}
          title="No Reconstruction Target Selected"
          description="Select an employee and target timestamp above, or choose a historical event from the mutation timeline."
          portalTheme="auditor"
        />
      )}
    </div>
  );
}
