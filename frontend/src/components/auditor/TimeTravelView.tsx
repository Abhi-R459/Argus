import { useState, useEffect, useRef, useMemo } from 'react';
import { useSearchParams, Link } from 'react-router-dom';
import { useAuth } from '@clerk/clerk-react';
import { useQuery } from '@tanstack/react-query';
import {
  History,
  Search,
  CalendarClock,
  CheckCircle2,
  Clock,
  GitCommit,
  ArrowRight,
  ExternalLink,
  X,
  AlertTriangle,
  RotateCcw,
  Sparkles,
  ChevronLeft,
  ChevronRight,
  TrendingUp,
  UserCheck,
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

/**
 * Formats a clean ISO UTC timestamp from date & time input strings with sub-second ceiling.
 * - If user enters HH:mm (e.g. 17:21), ceiling to 17:21:59.999999Z so mutations during that minute are captured.
 * - If user enters HH:mm:ss (e.g. 17:21:23), ceiling to 17:21:23.999999Z so microsecond-stamped mutations within that second are captured.
 * - If user provides an exact ISO string or timestamp with milliseconds, returns it cleanly.
 */
function buildTargetTimestamp(dateStr: string, timeStr: string): string {
  const cleanTime = timeStr.trim();
  if (/^\d{2}:\d{2}$/.test(cleanTime)) {
    return `${dateStr}T${cleanTime}:59.999999Z`;
  }
  if (/^\d{2}:\d{2}:\d{2}$/.test(cleanTime)) {
    return `${dateStr}T${cleanTime}.999999Z`;
  }
  if (/^\d{2}:\d{2}:\d{2}\.\d+/.test(cleanTime)) {
    const withoutZ = cleanTime.replace(/Z$/i, '');
    return `${dateStr}T${withoutZ}Z`;
  }
  if (cleanTime.includes('T')) {
    return cleanTime;
  }
  return `${dateStr}T${cleanTime}Z`;
}

function getMutationSemanticNote(log: AuditLogItem) {
  if (log.table_name === 'employees') {
    if (log.action === 'INSERT') return 'Initial Employee Registration & System Onboarding';
    if (log.action === 'UPDATE') {
      const oldRole = log.old_value?.role_id;
      const newRole = log.new_value?.role_id;
      if (oldRole !== undefined && newRole !== undefined && oldRole !== newRole) {
        return `Role Promotion / Reassignment (Role #${oldRole} → Role #${newRole})`;
      }
      return 'Employee Profile Attributes Modified';
    }
    if (log.action === 'DELETE') return 'Employee Record Deactivated / Archived';
  }
  if (log.table_name === 'salary_history') {
    const amt = (log.new_value as any)?.amount;
    const eff = (log.new_value as any)?.effective_date;
    const formatted = amt ? formatINR(Number(amt)) : 'Rate Adjustment';
    return `Compensation Updated to ${formatted}${eff ? ` (Effective: ${eff})` : ''}`;
  }
  return `${log.action} on ${log.table_name}`;
}

export default function TimeTravelView() {
  const { getToken } = useAuth();
  const [searchParams, setSearchParams] = useSearchParams();

  const [employeeIdInput, setEmployeeIdInput] = useState('');
  const [dateInput, setDateInput] = useState('');
  const [timeInput, setTimeInput] = useState('');
  const [activeTimestamp, setActiveTimestamp] = useState<string | null>(null);
  const [queryParams, setQueryParams] = useState<{ id: number; timestamp: string; sequenceId?: number | null } | null>(null);
  const [formError, setFormError] = useState<string | null>(null);
  const [reconstructingSeq, setReconstructingSeq] = useState<number | null>(null);
  const [feedbackToast, setFeedbackToast] = useState<{
    text: string;
    seq?: number | null;
    timestamp?: string;
  } | null>(null);

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
  }, [searchQuery, isDropdownOpen]);

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

  // ── Preloaded Directory for Instant Typeahead Matching (0ms Latency) ────────
  const {
    data: directoryData,
    isLoading: isDirectoryLoading,
  } = useQuery({
    queryKey: ['timeTravelDirectory'],
    queryFn: () => fetchEmployees(getToken, 100),
    staleTime: 60000,
  });

  const directoryEmployees: EmployeeListItem[] = directoryData?.items || [];

  // ── Fallback Dynamic Server Search Query (for directories > 100) ────────────
  const {
    data: searchResultsData,
  } = useQuery({
    queryKey: ['employeesSearch', debouncedSearchQuery],
    queryFn: () => fetchEmployees(getToken, 20, debouncedSearchQuery || undefined),
    enabled: isDropdownOpen && debouncedSearchQuery.trim().length > 0,
    staleTime: 30000,
  });

  // ── Synchronous Typeahead Matching (Filters Instantly While Typing) ──────────
  const matchingEmployees: EmployeeListItem[] = useMemo(() => {
    const q = searchQuery.trim();
    if (!q) {
      return directoryEmployees.slice(0, 10);
    }

    const qLower = q.toLowerCase();
    const cleanNumStr = q.replace(/^#/, '').replace(/^emp-?/i, '').trim();
    const isNum = /^\d+$/.test(cleanNumStr);
    const numVal = isNum ? parseInt(cleanNumStr, 10) : null;

    // 1. Filter preloaded directory in memory immediately
    const inMemoryMatches = directoryEmployees.filter((emp) => {
      if (numVal !== null && emp.employee_id === numVal) return true;
      if (cleanNumStr && String(emp.employee_id).includes(cleanNumStr)) return true;
      if (emp.full_name.toLowerCase().includes(qLower)) return true;
      if (emp.email.toLowerCase().includes(qLower)) return true;
      if (emp.role_title.toLowerCase().includes(qLower)) return true;
      if (emp.department_name.toLowerCase().includes(qLower)) return true;
      return false;
    });

    if (inMemoryMatches.length > 0) {
      return inMemoryMatches.slice(0, 10);
    }

    // 2. Fallback to server search results if no in-memory matches
    if (searchResultsData?.items && searchResultsData.items.length > 0) {
      return searchResultsData.items.slice(0, 10);
    }

    return [];
  }, [searchQuery, directoryEmployees, searchResultsData]);

  // ── Fetch Targeted Details for Currently Selected Employee ───────────────────
  const { data: selectedEmpData } = useQuery({
    queryKey: ['employeeDetail', parsedEmpId],
    queryFn: () => fetchEmployees(getToken, 1, String(parsedEmpId)),
    enabled: isValidEmpId,
    staleTime: 60000,
  });

  const selectedEmployee: EmployeeListItem | undefined =
    selectedEmpData?.items?.find((e) => e.employee_id === parsedEmpId) ||
    directoryEmployees.find((e) => e.employee_id === parsedEmpId) ||
    matchingEmployees.find((e) => e.employee_id === parsedEmpId);

  // ── Fetch Recent Audit Mutation Timeline for Selected Employee ─────────────
  const { data: employeeLogsData, isLoading: isLogsLoading } = useQuery({
    queryKey: ['employeeAuditLogs', parsedEmpId],
    queryFn: () => fetchAuditLogs({ employee_id: parsedEmpId, limit: 50 }, getToken),
    enabled: isValidEmpId,
    staleTime: 15000,
  });

  const employeeLogs: AuditLogItem[] = employeeLogsData?.items || [];

  const latestMutation = useMemo(() => {
    return employeeLogs.length > 0 ? employeeLogs[0] : null;
  }, [employeeLogs]);

  const initialMutation = useMemo(() => {
    if (employeeLogs.length === 0) return null;
    // Walk backwards from oldest to newest in the descending list
    for (let i = employeeLogs.length - 1; i >= 0; i--) {
      if (employeeLogs[i].table_name === 'employees' && employeeLogs[i].action.toUpperCase() === 'INSERT') {
        return employeeLogs[i];
      }
    }
    return employeeLogs[employeeLogs.length - 1];
  }, [employeeLogs]);

  // Find active log index corresponding to current queryParams
  const activeLogIndex = useMemo(() => {
    if (employeeLogs.length === 0) return -1;
    // 1. Primary match by sequence_id if available
    if (queryParams?.sequenceId !== undefined && queryParams.sequenceId !== null) {
      const seqIdx = employeeLogs.findIndex((l) => l.sequence_id === queryParams.sequenceId);
      if (seqIdx !== -1) return seqIdx;
    }
    // 2. Secondary match by timestamp
    if (!queryParams?.timestamp) return -1;
    const qNorm = queryParams.timestamp.trim().replace(' ', '+');
    const qTime = new Date(qNorm).getTime();
    return employeeLogs.findIndex((l) => {
      const lNorm = l.created_at.trim().replace(' ', '+');
      if (lNorm === qNorm) return true;
      const lTime = new Date(lNorm).getTime();
      return Math.abs(lTime - qTime) < 50;
    });
  }, [queryParams?.sequenceId, queryParams?.timestamp, employeeLogs]);

  // ── Parse URL Search Parameters on Mount / URL Changes ──────────────────────
  useEffect(() => {
    const urlEmpId = searchParams.get('emp_id');
    let urlAsOf = searchParams.get('as_of');
    const urlSeq = searchParams.get('seq');
    const parsedSeq = urlSeq ? parseInt(urlSeq, 10) : null;

    if (urlEmpId) {
      setEmployeeIdInput(urlEmpId);
    }

    if (urlAsOf) {
      // Normalize URL-decoded space turning +00:00 into " 00:00"
      if (urlAsOf.includes(' ') && !urlAsOf.includes('+')) {
        urlAsOf = urlAsOf.replace(' ', '+');
      }
      try {
        const d = new Date(urlAsOf);
        if (!isNaN(d.getTime())) {
          setDateInput(d.toISOString().split('T')[0]);
          const timePart = d.toISOString().split('T')[1];
          setTimeInput(timePart ? timePart.substring(0, 8) : '12:00:00');
          setActiveTimestamp(urlAsOf);
        }
      } catch {
        // Ignore date parsing failure
      }
    }

    if (urlEmpId && urlAsOf) {
      const parsed = parseInt(urlEmpId, 10);
      if (!isNaN(parsed) && parsed > 0) {
        setQueryParams({ id: parsed, timestamp: urlAsOf, sequenceId: parsedSeq });
      }
    }
  }, [searchParams]);

  // ── Time-Travel Query Execution ─────────────────────────────────────────────
  const { data: record, isLoading, isError, error } = useQuery({
    queryKey: ['timeTravel', queryParams?.id, queryParams?.timestamp, queryParams?.sequenceId],
    queryFn: async () => {
      if (!queryParams) return null;
      return fetchTimeTravelState(queryParams.id, queryParams.timestamp, getToken, queryParams.sequenceId);
    },
    enabled: !!queryParams,
    retry: false,
    refetchInterval: false,
  });

  // Clear in-flight reconstructing status and sync toast when query settles
  useEffect(() => {
    if (!isLoading && record) {
      const timer = setTimeout(() => {
        setReconstructingSeq(null);
      }, 180);
      return () => clearTimeout(timer);
    }
    if (isError) {
      setReconstructingSeq(null);
    }
  }, [isLoading, record, isError]);


  // Check if reconstructed state has historical differences from current employee state
  const isHistoricalDelta = useMemo(() => {
    if (!record || !selectedEmployee) return false;
    return (
      Math.abs(record.salary - (selectedEmployee.salary || 0)) > 0.01 ||
      record.role_title !== selectedEmployee.role_title ||
      record.is_active !== selectedEmployee.is_active ||
      record.department_name !== selectedEmployee.department_name
    );
  }, [record, selectedEmployee]);

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    setFormError(null);

    let targetId = isValidEmpId ? parsedEmpId : null;

    // If no employee selected via dropdown, try resolving from search query input
    if (!targetId && searchQuery.trim()) {
      const cleanNumStr = searchQuery.replace(/^#/, '').replace(/^emp-?/i, '').trim();
      if (/^\d+$/.test(cleanNumStr)) {
        targetId = parseInt(cleanNumStr, 10);
        setEmployeeIdInput(String(targetId));
      } else if (matchingEmployees.length > 0) {
        targetId = matchingEmployees[0].employee_id;
        setEmployeeIdInput(String(targetId));
      }
    }

    if (!targetId) {
      setFormError('Please select an employee from the workforce directory to reconstruct historical state.');
      return;
    }

    // Default empty date or time to now
    const now = new Date();
    const curDate = dateInput || now.toISOString().split('T')[0];
    const curTime = timeInput || now.toISOString().split('T')[1].substring(0, 8);
    if (!dateInput) setDateInput(curDate);
    if (!timeInput) setTimeInput(curTime);

    // If exact timestamp is stored and date matches, preserve it; otherwise build high-resolution timestamp
    let timestamp: string;
    if (activeTimestamp && activeTimestamp.startsWith(curDate)) {
      timestamp = activeTimestamp;
    } else {
      timestamp = buildTargetTimestamp(curDate, curTime);
    }

    setQueryParams({ id: targetId, timestamp, sequenceId: null });
    setSearchParams({ emp_id: String(targetId), as_of: timestamp });
    setFeedbackToast({
      text: `Reconstructing state as of ${curDate} ${curTime} UTC...`,
      seq: null,
      timestamp,
    });
  };

  const handleSelectEmployee = (idStr: string) => {
    setEmployeeIdInput(idStr);
    setFormError(null);
    if (!idStr) return;
    const id = parseInt(idStr, 10);

    // Default to current UTC time so any selected employee immediately reconstructs successfully
    const now = new Date();
    const curDate = now.toISOString().split('T')[0];
    const timePart = now.toISOString().split('T')[1];
    const curTime = timePart.substring(0, 8); // HH:mm:ss
    setDateInput(curDate);
    setTimeInput(curTime);
    setActiveTimestamp(null);
    setReconstructingSeq(null);

    const timestamp = now.toISOString();
    setQueryParams({ id, timestamp, sequenceId: null });
    setSearchParams({ emp_id: idStr, as_of: timestamp });
    setFeedbackToast({
      text: `Reconstructed live state for Employee #${id}`,
      seq: null,
      timestamp,
    });
  };

  const handleSetToNow = () => {
    const now = new Date();
    const curDate = now.toISOString().split('T')[0];
    const timePart = now.toISOString().split('T')[1];
    const curTime = timePart.substring(0, 8); // HH:mm:ss
    setDateInput(curDate);
    setTimeInput(curTime);
    setActiveTimestamp(null);
    setFormError(null);
    setReconstructingSeq(null);

    let id = parseInt(employeeIdInput, 10);
    // If no employee is selected yet, default to first directory employee
    if ((isNaN(id) || id <= 0) && directoryEmployees.length > 0) {
      id = directoryEmployees[0].employee_id;
      setEmployeeIdInput(String(id));
    }

    if (!isNaN(id) && id > 0) {
      const timestamp = now.toISOString();
      setQueryParams({ id, timestamp, sequenceId: null });
      setSearchParams({ emp_id: String(id), as_of: timestamp });
      setFeedbackToast({
        text: 'Reconstructed live current state (Now)',
        seq: null,
        timestamp,
      });
    }
  };

  const handleJumpToMutation = (createdAt: string, sequenceId?: number) => {
    try {
      const d = new Date(createdAt);
      if (!isNaN(d.getTime())) {
        const dateStr = d.toISOString().split('T')[0];
        const timePart = d.toISOString().split('T')[1] || '12:00:00.000Z';
        const timeStr = timePart.substring(0, 8);
        setDateInput(dateStr);
        setTimeInput(timeStr);
        setActiveTimestamp(createdAt);
        setFormError(null);

        if (sequenceId !== undefined && sequenceId !== null) {
          setReconstructingSeq(sequenceId);
        }

        let id = parseInt(employeeIdInput, 10);
        if ((isNaN(id) || id <= 0) && directoryEmployees.length > 0) {
          id = directoryEmployees[0].employee_id;
          setEmployeeIdInput(String(id));
        }

        if (!isNaN(id) && id > 0) {
          setQueryParams({ id, timestamp: createdAt, sequenceId: sequenceId ?? null });
          const newParams: Record<string, string> = { emp_id: String(id), as_of: createdAt };
          if (sequenceId !== undefined && sequenceId !== null) {
            newParams.seq = String(sequenceId);
          }
          setSearchParams(newParams);
          setFeedbackToast({
            text: sequenceId
              ? `Reconstructing state as of Seq #${sequenceId}...`
              : `Reconstructing state as of ${new Date(createdAt).toUTCString()}...`,
            seq: sequenceId,
            timestamp: createdAt,
          });
        }
      }
    } catch {
      // Fallback
    }
  };

  const handleStepLog = (direction: 'newer' | 'older') => {
    if (employeeLogs.length === 0) return;
    let targetIdx = 0;
    if (activeLogIndex === -1) {
      targetIdx = direction === 'older' ? 0 : employeeLogs.length - 1;
    } else {
      targetIdx = direction === 'newer' ? activeLogIndex - 1 : activeLogIndex + 1;
    }

    if (targetIdx >= 0 && targetIdx < employeeLogs.length) {
      const targetLog = employeeLogs[targetIdx];
      handleJumpToMutation(targetLog.created_at, targetLog.sequence_id);
    }
  };


  return (
    <div className="space-y-6 animate-fade-cascade">
      {/* Header & Controls */}
      <div className="bg-linear-surface-1 border border-linear-hairline rounded-2xl p-6 shadow-xs relative z-20">
        {/* Dedicated overflow container for the watermark icon so dropdown menus are never clipped */}
        <div className="absolute inset-0 rounded-2xl overflow-hidden pointer-events-none" aria-hidden="true">
          <div className="absolute top-0 right-0 p-8 opacity-5">
            <History className="w-32 h-32" />
          </div>
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

        <form onSubmit={handleSearch} autoComplete="off" className="space-y-4 max-w-5xl relative z-10">
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-12 gap-4 items-end">
            
            {/* Employee Selector Autocomplete Combobox */}
            <div ref={searchContainerRef} className="sm:col-span-2 lg:col-span-5 relative z-30">
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
                    id="timetravel-employee-search"
                    name="search"
                    type="text"
                    role="combobox"
                    autoComplete="off"
                    autoCorrect="off"
                    autoCapitalize="off"
                    spellCheck={false}
                    data-lpignore="true"
                    data-form-type="other"
                    data-1p-ignore="true"
                    aria-expanded={isDropdownOpen}
                    aria-autocomplete="list"
                    aria-controls="employee-search-listbox"
                    aria-activedescendant={
                      activeOptionIndex >= 0 && matchingEmployees[activeOptionIndex]
                        ? `employee-option-${matchingEmployees[activeOptionIndex].employee_id}`
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
                        } else if (matchingEmployees.length > 0) {
                          setActiveOptionIndex((prev) => (prev < matchingEmployees.length - 1 ? prev + 1 : 0));
                        }
                      } else if (e.key === 'ArrowUp') {
                        e.preventDefault();
                        if (isDropdownOpen && matchingEmployees.length > 0) {
                          setActiveOptionIndex((prev) => (prev > 0 ? prev - 1 : matchingEmployees.length - 1));
                        }
                      } else if (e.key === 'Enter') {
                        if (isDropdownOpen) {
                          e.preventDefault();
                          const targetEmp =
                            activeOptionIndex >= 0 && activeOptionIndex < matchingEmployees.length
                              ? matchingEmployees[activeOptionIndex]
                              : matchingEmployees[0];
                          if (targetEmp) {
                            handleSelectEmployee(String(targetEmp.employee_id));
                            setIsDropdownOpen(false);
                            setSearchQuery('');
                          }
                        }
                      }
                    }}
                    placeholder="Search personnel by name, role, department, or #ID..."
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

              {/* Floating Match Dropdown with High Elevation & Crisp Contrast */}
              {isDropdownOpen && (
                <div
                  id="employee-search-listbox"
                  role="listbox"
                  aria-label="Matching Personnel"
                  className="absolute left-0 right-0 top-full mt-1.5 z-50 bg-[#16181d] border border-linear-hairline-strong rounded-xl shadow-2xl backdrop-blur-xl ring-1 ring-black/60 overflow-hidden max-h-72 overflow-y-auto animate-in fade-in slide-in-from-top-1 duration-150 origin-top"
                >
                  {isDirectoryLoading && directoryEmployees.length === 0 ? (
                    <div className="p-4 text-center text-xs text-linear-ink-muted flex items-center justify-center gap-2">
                      <div className="w-3.5 h-3.5 border-2 border-linear-primary border-t-transparent rounded-full animate-fast-spin" />
                      Loading workforce directory...
                    </div>
                  ) : matchingEmployees.length === 0 ? (
                    <div className="p-4 text-center text-xs text-linear-ink-muted">
                      No employees found matching <strong className="text-linear-ink font-mono">"{searchQuery || debouncedSearchQuery || '...'}"</strong>
                    </div>
                  ) : (
                    <div className="py-1 divide-y divide-linear-hairline/40">
                      <div className="px-3 py-1.5 text-[10px] font-mono text-linear-ink-subtle uppercase tracking-wider bg-linear-surface-2/70 flex justify-between">
                        <span>Matching Personnel ({matchingEmployees.length})</span>
                        <span className="text-linear-ink-subtle lowercase">↑↓ navigate • ↵ select • esc close</span>
                      </div>
                      {matchingEmployees.map((emp, idx) => (
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
                              ? 'bg-linear-primary/20 text-linear-ink border-l-2 border-linear-primary'
                              : 'hover:bg-linear-surface-2/80 text-linear-ink border-l-2 border-transparent'
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
                onChange={(e) => {
                  setDateInput(e.target.value);
                  setActiveTimestamp(null);
                  setFormError(null);
                }}
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
                  className="text-[11px] text-linear-primary hover:text-linear-primary-hover font-mono hover:underline focus-visible:outline-none cursor-pointer btn-press active:scale-90 transition-all duration-150"
                >
                  Set Now
                </button>
              </div>
              <input
                type="time"
                step="1"
                required
                value={timeInput}
                onChange={(e) => {
                  setTimeInput(e.target.value);
                  setActiveTimestamp(null);
                  setFormError(null);
                }}
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
                className="w-full h-[42px] rounded-xl font-medium text-xs btn-press active:scale-95 transition-all duration-150"
              >
                Reconstruct
              </Button>
            </div>

          </div>

          {/* Validation Form Error Alert */}
          {formError && (
            <div className="p-3 rounded-xl bg-rose-500/10 border border-rose-500/30 text-rose-300 text-xs flex items-center gap-2 animate-in fade-in duration-150">
              <AlertTriangle className="w-4 h-4 text-rose-400 shrink-0" />
              <span>{formError}</span>
            </div>
          )}

          {/* Quick Select Chips when no employee is selected */}
          {!isValidEmpId && directoryEmployees.length > 0 && (
            <div className="p-3.5 rounded-xl bg-linear-surface-2/40 border border-linear-hairline space-y-2">
              <div className="text-xs text-linear-ink-muted flex items-center gap-1.5">
                <Sparkles className="w-3.5 h-3.5 text-linear-primary" />
                <span>Quick Select Audited Personnel:</span>
              </div>
              <div className="flex flex-wrap gap-2">
                {directoryEmployees.slice(0, 5).map((emp) => (
                  <button
                    key={emp.employee_id}
                    type="button"
                    onClick={() => handleSelectEmployee(String(emp.employee_id))}
                    className="px-2.5 py-1 rounded-lg bg-linear-canvas hover:bg-linear-primary/15 border border-linear-hairline hover:border-linear-primary/40 text-xs text-linear-ink transition-all duration-150 flex items-center gap-2 cursor-pointer group btn-press active:scale-95"
                  >
                    <div className="w-4 h-4 rounded bg-linear-primary/10 text-linear-primary font-bold text-[9px] flex items-center justify-center">
                      #{emp.employee_id}
                    </div>
                    <span className="font-medium group-hover:text-linear-primary transition-colors">{emp.full_name}</span>
                    <span className="text-[10px] text-linear-ink-subtle">{emp.role_title}</span>
                  </button>
                ))}
              </div>
            </div>
          )}

          {/* Quick Presets & Ledger Bounds for Selected Employee */}
          {isValidEmpId && (
            <div className="space-y-2 pt-2 border-t border-linear-hairline/60">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <div className="flex flex-wrap items-center gap-2">
                  <span className="text-[11px] text-linear-ink-subtle uppercase tracking-wider font-mono">Presets:</span>
                  <button
                    type="button"
                    onClick={handleSetToNow}
                    className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg border text-xs font-mono transition-all duration-150 cursor-pointer btn-press active:scale-95 ${
                      activeLogIndex === -1 && record
                        ? 'bg-linear-primary/20 text-linear-primary border-linear-primary/50 ring-1 ring-linear-primary/30'
                        : 'bg-linear-surface-2 hover:bg-linear-surface-3 border-linear-hairline text-linear-ink'
                    }`}
                  >
                    <Clock className="w-3 h-3 text-linear-primary" />
                    <span>Now (Current Live State)</span>
                  </button>
                  {latestMutation && (
                    <button
                      type="button"
                      onClick={() => handleJumpToMutation(latestMutation.created_at, latestMutation.sequence_id)}
                      className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg border text-xs font-mono transition-all duration-150 cursor-pointer btn-press active:scale-95 ${
                        activeLogIndex === 0
                          ? 'bg-linear-primary/20 text-linear-primary border-linear-primary/50 ring-1 ring-linear-primary/30'
                          : 'bg-linear-surface-2 hover:bg-linear-surface-3 border-linear-hairline text-linear-ink'
                      }`}
                    >
                      <GitCommit className="w-3 h-3 text-linear-primary" />
                      <span>Latest Mutation (Seq #{latestMutation.sequence_id})</span>
                    </button>
                  )}
                  {initialMutation && initialMutation !== latestMutation && (
                    <button
                      type="button"
                      onClick={() => handleJumpToMutation(initialMutation.created_at, initialMutation.sequence_id)}
                      className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg border text-xs font-mono transition-all duration-150 cursor-pointer btn-press active:scale-95 ${
                        activeLogIndex === employeeLogs.length - 1
                          ? 'bg-amber-500/20 text-amber-300 border-amber-500/50 ring-1 ring-amber-500/30'
                          : 'bg-linear-surface-2 hover:bg-linear-surface-3 border-linear-hairline text-linear-ink'
                      }`}
                    >
                      <Sparkles className="w-3 h-3 text-amber-400" />
                      <span>Initial Creation (Seq #{initialMutation.sequence_id})</span>
                    </button>
                  )}
                </div>

                {initialMutation && (
                  <div className="flex items-center gap-1.5 text-[11px] font-mono text-linear-ink-subtle">
                    <span>Ledger Origin: </span>
                    <span className="text-amber-300 font-semibold">{new Date(initialMutation.created_at).toUTCString().replace(' GMT', ' UTC')}</span>
                    <span>(Seq #{initialMutation.sequence_id})</span>
                  </div>
                )}
              </div>
            </div>
          )}
        </form>
      </div>

      {/* Historical Audit Mutation Timeline for Selected Employee */}
      {isValidEmpId && (
        <div className="bg-linear-surface-1 border border-linear-hairline rounded-2xl p-5 shadow-sm">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-3 mb-3 border-b border-linear-hairline">
            <div className="flex items-center space-x-2">
              <Clock className="w-4 h-4 text-linear-primary" />
              <h3 className="text-sm font-semibold text-linear-ink">
                Historical Mutation Timeline for Employee #{parsedEmpId}
              </h3>
              {selectedEmployee && (
                <span className="text-xs text-linear-ink-muted">({selectedEmployee.full_name})</span>
              )}
              {employeeLogs.length > 0 && (
                <span className="text-xs font-mono px-2 py-0.5 rounded-full bg-linear-surface-2 text-linear-ink-muted border border-linear-hairline">
                  {employeeLogs.length} ledger event{employeeLogs.length === 1 ? '' : 's'}
                </span>
              )}
            </div>

            {/* Step Navigation Controls */}
            {employeeLogs.length > 1 && (
              <div className="flex items-center gap-2">
                <span className="text-xs text-linear-ink-subtle">Step Through:</span>
                <button
                  type="button"
                  disabled={activeLogIndex <= 0}
                  onClick={() => handleStepLog('newer')}
                  title="Step to newer audit event"
                  className="px-2.5 py-1 rounded-lg bg-linear-surface-2 hover:bg-linear-surface-3 disabled:opacity-30 disabled:pointer-events-none border border-linear-hairline text-xs text-linear-ink font-mono flex items-center gap-1 transition-all duration-150 cursor-pointer btn-press active:scale-90"
                >
                  <ChevronLeft className="w-3.5 h-3.5" /> Newer
                </button>
                <button
                  type="button"
                  disabled={activeLogIndex >= employeeLogs.length - 1 || activeLogIndex === -1}
                  onClick={() => handleStepLog('older')}
                  title="Step to older audit event"
                  className="px-2.5 py-1 rounded-lg bg-linear-surface-2 hover:bg-linear-surface-3 disabled:opacity-30 disabled:pointer-events-none border border-linear-hairline text-xs text-linear-ink font-mono flex items-center gap-1 transition-all duration-150 cursor-pointer btn-press active:scale-90"
                >
                  Older <ChevronRight className="w-3.5 h-3.5" />
                </button>
              </div>
            )}
          </div>

          {/* Micro-Interaction Toast / Activity Feedback Banner */}
          {feedbackToast && (
            <div className="mb-3 px-3.5 py-2 rounded-xl bg-emerald-950/40 border border-emerald-500/40 flex items-center justify-between gap-3 text-xs font-mono text-emerald-300 animate-badge-slide shadow-sm">
              <div className="flex items-center gap-2 min-w-0">
                {reconstructingSeq ? (
                  <div className="w-3.5 h-3.5 border-2 border-emerald-400 border-t-transparent rounded-full animate-fast-spin shrink-0" />
                ) : (
                  <CheckCircle2 className="w-4 h-4 text-emerald-400 animate-check-pop shrink-0" />
                )}
                <span className="truncate">{feedbackToast.text}</span>
              </div>
              {feedbackToast.seq && (
                <span className="text-[10px] px-2 py-0.5 rounded bg-emerald-500/20 border border-emerald-500/30 text-emerald-300 font-bold shrink-0">
                  Seq #{feedbackToast.seq}
                </span>
              )}
            </div>
          )}

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
              {employeeLogs.map((log, idx) => {
                const isCardActive = idx === activeLogIndex;
                const isCardReconstructing = reconstructingSeq === log.sequence_id;
                const semanticNote = getMutationSemanticNote(log);

                return (
                  <div
                    key={log.sequence_id}
                    onClick={(e) => {
                      if ((e.target as HTMLElement).closest('a')) return;
                      handleJumpToMutation(log.created_at, log.sequence_id);
                    }}
                    className={`rounded-xl p-3.5 transition-all duration-200 flex flex-col justify-between space-y-3 relative overflow-hidden cursor-pointer btn-press active:scale-[0.985] ${
                      isCardReconstructing
                        ? 'bg-emerald-950/40 border-2 border-emerald-400 shadow-xl shadow-emerald-500/25 ring-2 ring-emerald-400/50'
                        : isCardActive
                        ? 'bg-emerald-950/30 border-2 border-emerald-500/90 shadow-lg shadow-emerald-500/15 ring-1 ring-emerald-400/40 animate-card-target'
                        : 'bg-linear-canvas hover:bg-linear-surface-2/80 border border-linear-hairline hover:border-linear-hairline-strong'
                    }`}
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
                      <div className="flex items-center gap-1.5">
                        {isCardActive && (
                          <span className="text-[10px] font-mono px-2 py-0.5 rounded-full bg-emerald-500/20 text-emerald-400 border border-emerald-500/40 flex items-center gap-1.5 font-semibold animate-badge-slide">
                            <span className="relative flex h-2 w-2">
                              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75" />
                              <span className="relative inline-flex rounded-full h-2 w-2 bg-emerald-500" />
                            </span>
                            Target
                          </span>
                        )}
                        <span className="text-[10px] text-linear-ink-subtle font-mono">
                          {log.table_name}
                        </span>
                      </div>
                    </div>

                    <div className="space-y-1">
                      <p className="text-xs font-medium text-linear-ink leading-snug">
                        {semanticNote}
                      </p>
                      <div className="text-[11px] text-linear-ink-muted flex items-center justify-between font-mono">
                        <span>Actor: {log.actor_name}</span>
                        <span className="text-[10px] text-linear-ink-subtle">
                          {new Date(log.created_at).toLocaleTimeString()}
                        </span>
                      </div>
                      <span className="text-[10px] text-linear-ink-subtle font-mono block">
                        {new Date(log.created_at).toISOString()}
                      </span>
                    </div>

                    <div className="pt-2 border-t border-linear-hairline flex items-center justify-between gap-2">
                      <button
                        type="button"
                        onClick={(e) => {
                          e.stopPropagation();
                          handleJumpToMutation(log.created_at, log.sequence_id);
                        }}
                        className={`text-[11px] font-medium flex items-center group cursor-pointer focus-visible:outline-none focus-visible:underline text-left btn-press active:scale-95 transition-all duration-150 ${
                          isCardActive
                            ? 'text-emerald-400 font-semibold'
                            : isCardReconstructing
                            ? 'text-emerald-300 font-semibold'
                            : 'text-linear-primary hover:text-linear-primary-hover'
                        }`}
                      >
                        {isCardReconstructing ? (
                          <span className="flex items-center gap-1.5 text-emerald-300 animate-pulse">
                            <div className="w-3.5 h-3.5 border-2 border-emerald-400 border-t-transparent rounded-full animate-fast-spin" />
                            <span>Reconstructing...</span>
                          </span>
                        ) : isCardActive ? (
                          <span className="flex items-center gap-1.5">
                            <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400 animate-check-pop" />
                            <span>Currently Reconstructed</span>
                          </span>
                        ) : (
                          <>
                            <span className="group-hover:underline">Reconstruct this state</span>
                            <ArrowRight className="w-3 h-3 ml-1 group-hover:translate-x-1 group-active:translate-x-1.5 transition-transform duration-150" />
                          </>
                        )}
                      </button>
                      <div className="flex items-center space-x-1 shrink-0" onClick={(e) => e.stopPropagation()}>
                        <Link
                          to={`/auditor/chain?seq=${log.sequence_id}`}
                          title="Inspect in Chain Explorer"
                          className="text-linear-ink-subtle hover:text-linear-primary p-1 rounded transition-colors duration-150 focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-linear-primary btn-press active:scale-90"
                        >
                          <GitCommit className="w-3.5 h-3.5" />
                        </Link>
                        <Link
                          to={`/auditor/log?seq=${log.sequence_id}`}
                          title="View in Audit Log"
                          className="text-linear-ink-subtle hover:text-linear-primary p-1 rounded transition-colors duration-150 focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-linear-primary btn-press active:scale-90"
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
        <div className="bg-amber-500/10 border border-amber-500/30 rounded-2xl p-5 text-linear-ink animate-fade-cascade space-y-4">
          <div className="flex items-start gap-3">
            <AlertTriangle className="w-5 h-5 text-amber-400 mt-0.5 shrink-0" />
            <div className="space-y-1.5 flex-1">
              <h3 className="font-semibold text-sm text-amber-400 flex items-center gap-2">
                <span>
                  {error instanceof Error && error.message.toLowerCase().includes('did not exist as of')
                    ? 'Historical State Not Found (Target Timestamp Prior to Genesis)'
                    : 'Reconstruction Failed'}
                </span>
              </h3>
              <p className="text-xs text-linear-ink opacity-90 leading-relaxed font-mono">
                {error instanceof Error
                  ? error.message
                  : 'The requested record could not be reconstructed for the given timestamp.'}
              </p>
              {error instanceof Error && error.message.toLowerCase().includes('did not exist as of') && (
                <p className="text-xs text-linear-ink-muted leading-relaxed">
                  The queried target timestamp is earlier than the first audit log entry recorded for this employee.
                  Historical time-travel cannot reconstruct records prior to their cryptographic registration in the ledger.
                </p>
              )}
              {initialMutation && (
                <div className="text-xs text-linear-ink font-mono bg-linear-canvas/80 border border-linear-hairline px-3 py-2 rounded-xl w-fit mt-2">
                  <span className="text-linear-ink-muted">First recorded ledger event: </span>
                  <strong className="text-linear-primary">{initialMutation.action}</strong>
                  <span className="text-linear-ink-muted"> at </span>
                  <span className="text-amber-300 font-semibold">{new Date(initialMutation.created_at).toUTCString()}</span>
                  <span className="text-linear-ink-subtle"> (Seq #{initialMutation.sequence_id})</span>
                </div>
              )}
            </div>
          </div>

          {/* Quick Recovery Actions */}
          <div className="pt-3 border-t border-linear-hairline/60 flex flex-wrap items-center gap-2.5">
            <span className="text-xs text-linear-ink-muted font-medium">Quick Recovery:</span>
            {initialMutation && (
              <button
                type="button"
                onClick={() => handleJumpToMutation(initialMutation.created_at, initialMutation.sequence_id)}
                className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-amber-500/20 hover:bg-amber-500/30 text-amber-300 border border-amber-500/40 text-xs font-medium transition-all duration-150 cursor-pointer btn-press active:scale-95"
              >
                <Sparkles className="w-3.5 h-3.5" />
                <span>Reconstruct at Initial Creation (Seq #{initialMutation.sequence_id})</span>
              </button>
            )}
            <button
              type="button"
              onClick={handleSetToNow}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-linear-primary/20 hover:bg-linear-primary/30 text-linear-primary border border-linear-primary/40 text-xs font-medium transition-all duration-150 cursor-pointer btn-press active:scale-95"
            >
              <RotateCcw className="w-3.5 h-3.5" />
              <span>Reconstruct Current State (Now)</span>
            </button>
          </div>
        </div>
      )}

      {record && !isLoading && (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 animate-fade-cascade items-stretch">
          {/* Formatted View */}
          <div className="lg:col-span-2 bg-linear-surface-1 border border-linear-hairline rounded-2xl shadow-xs overflow-hidden flex flex-col justify-between">
            <div>
              <div className="bg-linear-surface-2/40 px-6 py-4 border-b border-linear-hairline flex flex-col sm:flex-row sm:items-center justify-between gap-2">
                <div className="flex items-center gap-2">
                  <CheckCircle2 className="w-4 h-4 text-linear-success shrink-0" />
                  <h3 className="font-semibold text-linear-ink text-sm">
                    State Reconstructed Successfully
                  </h3>
                  {isHistoricalDelta ? (
                    <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md text-[10px] font-mono font-medium bg-amber-500/15 text-amber-300 border border-amber-500/30">
                      <TrendingUp className="w-3 h-3" /> Past Delta Detected
                    </span>
                  ) : (
                    <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md text-[10px] font-mono font-medium bg-emerald-500/15 text-emerald-400 border border-emerald-500/30">
                      <UserCheck className="w-3 h-3" /> Matches Live State
                    </span>
                  )}
                </div>
                <div className="flex items-center text-xs font-mono text-linear-primary bg-linear-primary/15 px-3 py-1 rounded-md border border-linear-primary/30">
                  <CalendarClock className="w-3 h-3 mr-2" />
                  <span>AS OF {new Date(record.as_of).toLocaleString()} UTC</span>
                  {record.sequence_id && (
                    <span className="ml-1.5 font-bold text-emerald-400">· Seq #{record.sequence_id}</span>
                  )}
                </div>
              </div>

              <div className="p-6">
                <div className="grid grid-cols-2 gap-x-12 gap-y-6">
                  <div>
                    <div className="text-xs font-medium text-linear-ink-muted mb-1 uppercase tracking-wider">Employee ID</div>
                    <div className="text-lg font-mono text-linear-ink">#{record.employee_id}</div>
                  </div>
                  <div>
                    <div className="text-xs font-medium text-linear-ink-muted mb-1 uppercase tracking-wider">Status as of Timestamp</div>
                    <div className="flex items-center gap-2">
                      {record.is_active ? (
                        <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-linear-success/15 text-linear-success border border-linear-success/30">
                          Active
                        </span>
                      ) : (
                        <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-grafana-orange/15 text-grafana-orange border border-grafana-orange/30">
                          Inactive
                        </span>
                      )}
                      {selectedEmployee && record.is_active !== selectedEmployee.is_active && (
                        <span className="text-xs text-linear-ink-subtle">
                          (Current Live: {selectedEmployee.is_active ? 'Active' : 'Inactive'})
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
                    <div className="text-base text-linear-ink-muted font-mono text-xs">{record.email}</div>
                  </div>

                  <div>
                    <div className="text-xs font-medium text-linear-ink-muted mb-1 uppercase tracking-wider">Role & Department</div>
                    <div className="text-base text-linear-ink font-medium">{record.role_title}</div>
                    <div className="text-sm text-linear-ink-muted">{record.department_name}</div>
                    {selectedEmployee && record.role_title !== selectedEmployee.role_title && (
                      <div className="text-[11px] text-amber-400 font-mono mt-1">
                        Current Live Role: {selectedEmployee.role_title}
                      </div>
                    )}
                  </div>
                  <div>
                    <div className="text-xs font-medium text-linear-ink-muted mb-1 uppercase tracking-wider">Historical Compensation</div>
                    <div className="text-lg font-mono text-linear-ink font-semibold">
                      {formatINR(record.salary)}
                    </div>
                    {selectedEmployee && selectedEmployee.salary && Math.abs(record.salary - selectedEmployee.salary) > 0.01 && (
                      <div className="text-[11px] text-linear-ink-muted font-mono mt-1">
                        Current Live: <span className="text-linear-primary font-semibold">{formatINR(selectedEmployee.salary)}</span>
                        {' '}({record.salary < selectedEmployee.salary ? '-' : '+'}{formatINR(Math.abs(record.salary - selectedEmployee.salary))})
                      </div>
                    )}
                  </div>

                  <div className="col-span-2">
                    <div className="text-xs font-medium text-linear-ink-muted mb-1 uppercase tracking-wider">Official Date Hired</div>
                    <div className="text-sm text-linear-ink font-mono">{record.date_hired}</div>
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
