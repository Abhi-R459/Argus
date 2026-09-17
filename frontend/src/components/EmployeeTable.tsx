import { useState, useEffect, useRef } from 'react';
import { useQuery } from '@tanstack/react-query';
import { useAuth } from '@clerk/clerk-react';
import {
  Search,
  ChevronLeft,
  ChevronRight,
  Edit3,
  DollarSign,
  User,
  ShieldCheck,
  Building2,
} from 'lucide-react';
import { fetchWithAuth } from '../lib/api';
import { fetchDepartments, type DepartmentItem } from '../services/auditService';
import { DataTable } from './common/DataTable';
import { FilterBar, type ActiveFilterItem } from './common/FilterBar';
import { Button } from './common/Button';
import { SkeletonRows } from './common/SkeletonRows';
import { useKeyboardNav } from '../hooks/useKeyboardNav';
import { EmployeeSheet, type Employee } from './hr/EmployeeSheet';

interface PaginatedResponse {
  items: Employee[];
  total: number;
  page: number;
  pages: number;
}

export default function EmployeeTable() {
  const { getToken } = useAuth();
  const searchInputRef = useRef<HTMLInputElement | null>(null);

  const [page, setPage] = useState(1);
  const [search, setSearch] = useState('');
  const [debouncedSearch, setDebouncedSearch] = useState('');
  const [selectedDept, setSelectedDept] = useState<string>('all');
  const [selectedStatus, setSelectedStatus] = useState<'all' | 'active' | 'inactive'>('all');

  // Sheet inspector state
  const [selectedEmployee, setSelectedEmployee] = useState<Employee | null>(null);
  const [isSheetOpen, setIsSheetOpen] = useState(false);
  const [sheetTab, setSheetTab] = useState<'overview' | 'edit' | 'salary'>('overview');
  const [focusedRowIndex, setFocusedRowIndex] = useState<number>(0);

  // Debounce search query
  useEffect(() => {
    const handler = setTimeout(() => {
      setDebouncedSearch(search);
      setPage(1);
    }, 350);
    return () => clearTimeout(handler);
  }, [search]);

  const limit = 12;

  // Query employees
  const { data, isLoading, isError, isFetching } = useQuery<PaginatedResponse>({
    queryKey: ['employees', page, debouncedSearch],
    queryFn: () =>
      fetchWithAuth(
        `/employees?page=${page}&limit=${limit}${
          debouncedSearch ? `&search=${encodeURIComponent(debouncedSearch)}` : ''
        }`,
        {},
        getToken
      ),
    placeholderData: (prev) => prev,
    refetchInterval: 3000,
  });

  // Query departments for filtering
  const { data: departments = [] } = useQuery<DepartmentItem[]>({
    queryKey: ['departments'],
    queryFn: () => fetchDepartments(() => getToken()),
    staleTime: 300000,
  });

  const rawItems = data?.items ?? [];

  // Filter client-side by department and status
  const filteredItems = rawItems.filter((emp) => {
    if (selectedDept !== 'all' && emp.department_name !== selectedDept) return false;
    if (selectedStatus === 'active' && !emp.is_active) return false;
    if (selectedStatus === 'inactive' && emp.is_active) return false;
    return true;
  });

  // Active filters list for FilterBar
  const activeFilters: ActiveFilterItem[] = [];
  if (search) {
    activeFilters.push({
      id: 'search',
      label: 'Search',
      value: search,
      onRemove: () => {
        setSearch('');
        setDebouncedSearch('');
      },
    });
  }
  if (selectedDept !== 'all') {
    activeFilters.push({
      id: 'dept',
      label: 'Department',
      value: selectedDept,
      onRemove: () => setSelectedDept('all'),
    });
  }
  if (selectedStatus !== 'all') {
    activeFilters.push({
      id: 'status',
      label: 'Status',
      value: selectedStatus === 'active' ? 'Active' : 'Deactivated',
      onRemove: () => setSelectedStatus('all'),
    });
  }

  const handleClearAll = () => {
    setSearch('');
    setDebouncedSearch('');
    setSelectedDept('all');
    setSelectedStatus('all');
    setPage(1);
  };

  // Keyboard navigation
  useKeyboardNav({
    itemCount: filteredItems.length,
    selectedIndex: focusedRowIndex,
    onSelectIndex: (idx) => setFocusedRowIndex(idx),
    onPeek: (idx) => {
      const emp = filteredItems[idx];
      if (emp) {
        setSelectedEmployee(emp);
        setSheetTab('overview');
        setIsSheetOpen(true);
      }
    },
    onDismiss: () => setIsSheetOpen(false),
    searchInputRef,
    enabled: true,
  });

  const openSheet = (emp: Employee, tab: 'overview' | 'edit' | 'salary' = 'overview') => {
    setSelectedEmployee(emp);
    setSheetTab(tab);
    setIsSheetOpen(true);
  };

  return (
    <div className="space-y-3">
      {/* Faceted Filter Toolbar */}
      <FilterBar activeFilters={activeFilters} onClearAll={handleClearAll} portalTheme="hr">
        <div className="flex flex-wrap items-center gap-2.5 flex-1">
          {/* Quick Search */}
          <div className="relative min-w-[220px] max-w-sm flex-1">
            <Search className="w-3.5 h-3.5 text-grafana-neutral absolute left-2.5 top-1/2 -translate-y-1/2 pointer-events-none" />
            <input
              ref={searchInputRef}
              type="text"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search personnel by name or email... (/)"
              className="w-full pl-8 pr-7 py-1.5 bg-white border border-grafana-border rounded-md text-xs text-grafana-ink placeholder-grafana-neutral focus:outline-none focus:border-grafana-orange focus:ring-1 focus:ring-grafana-orange/20 transition-colors shadow-2xs"
            />
            {search && (
              <button
                type="button"
                onClick={() => setSearch('')}
                aria-label="Clear search input"
                className="absolute right-2 top-1/2 -translate-y-1/2 text-xs text-grafana-neutral hover:text-grafana-ink p-1 rounded focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-grafana-orange"
              >
                ×
              </button>
            )}
          </div>

          {/* Department Filter */}
          <div className="relative flex items-center">
            <Building2 className="w-3.5 h-3.5 text-grafana-neutral absolute left-2 pointer-events-none" />
            <select
              value={selectedDept}
              onChange={(e) => setSelectedDept(e.target.value)}
              className="pl-7 pr-6 py-1.5 bg-white border border-grafana-border rounded-md text-xs text-grafana-ink focus:outline-none focus:border-grafana-orange cursor-pointer shadow-2xs"
            >
              <option value="all">All Departments</option>
              {departments.map((dept) => (
                <option key={dept.department_id} value={dept.name}>
                  {dept.name}
                </option>
              ))}
            </select>
          </div>

          {/* Status Filter */}
          <div className="flex items-center rounded-md border border-grafana-border p-0.5 bg-grafana-surface shadow-2xs text-xs">
            <button
              type="button"
              onClick={() => setSelectedStatus('all')}
              className={`px-2.5 py-1 rounded font-medium transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-grafana-orange ${
                selectedStatus === 'all'
                  ? 'bg-white text-grafana-ink shadow-2xs font-semibold'
                  : 'text-grafana-neutral hover:text-grafana-ink'
              }`}
            >
              All
            </button>
            <button
              type="button"
              onClick={() => setSelectedStatus('active')}
              className={`px-2.5 py-1 rounded font-medium transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-grafana-orange ${
                selectedStatus === 'active'
                  ? 'bg-white text-linear-success shadow-2xs font-semibold'
                  : 'text-grafana-neutral hover:text-grafana-ink'
              }`}
            >
              Active
            </button>
            <button
              type="button"
              onClick={() => setSelectedStatus('inactive')}
              className={`px-2.5 py-1 rounded font-medium transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-grafana-orange ${
                selectedStatus === 'inactive'
                  ? 'bg-white text-grafana-orange shadow-2xs font-semibold'
                  : 'text-grafana-neutral hover:text-grafana-ink'
              }`}
            >
              Deactivated
            </button>
          </div>
        </div>

        <div className="flex items-center gap-2 text-xs text-grafana-neutral font-mono">
          {isFetching && <span className="text-[10px] text-grafana-orange animate-pulse">syncing…</span>}
          <span>{filteredItems.length} records</span>
        </div>
      </FilterBar>

      {/* Main Table Container */}
      <DataTable.Root portalTheme="hr">
        <DataTable.Header portalTheme="hr">
          <DataTable.HeadCell className="w-[30%]">
            Employee Profile
          </DataTable.HeadCell>
          <DataTable.HeadCell className="w-[24%]">
            Role & Department
          </DataTable.HeadCell>
          <DataTable.HeadCell className="w-[16%]">
            Annual Compensation
          </DataTable.HeadCell>
          <DataTable.HeadCell className="w-[14%]">
            Security & Status
          </DataTable.HeadCell>
          <DataTable.HeadCell className="w-[16%] text-right">
            Actions
          </DataTable.HeadCell>
        </DataTable.Header>

        <DataTable.Body portalTheme="hr">
          {isLoading ? (
            <SkeletonRows rowCount={8} columnCount={5} portalTheme="hr" />
          ) : isError ? (
            <tr>
              <td colSpan={5} className="py-12 text-center text-xs text-grafana-orange font-mono">
                Failed to query employee directory from PostgreSQL engine.
              </td>
            </tr>
          ) : filteredItems.length === 0 ? (
            <tr>
              <td colSpan={5} className="py-12 text-center text-xs text-grafana-neutral">
                No employees found matching the specified parameters.
              </td>
            </tr>
          ) : (
            filteredItems.map((emp, idx) => {
              const isSelected = selectedEmployee?.employee_id === emp.employee_id;
              const isKeyboardFocused = focusedRowIndex === idx;

              return (
                <DataTable.Row
                  key={emp.employee_id}
                  portalTheme="hr"
                  isSelected={isSelected}
                  className={`${isKeyboardFocused ? 'ring-1 ring-inset ring-grafana-orange/40' : ''}`}
                  onClick={() => openSheet(emp, 'overview')}
                >
                  {/* Name & Email */}
                  <DataTable.Cell>
                    <div className="flex items-center gap-3">
                      <div className="w-8 h-8 rounded-lg bg-grafana-blue/10 border border-grafana-blue/20 flex items-center justify-center text-grafana-blue font-bold text-xs font-mono shrink-0">
                        {emp.full_name.charAt(0)}
                      </div>
                      <div className="min-w-0">
                        <div className="font-bold text-grafana-ink truncate flex items-center gap-1.5">
                          <span>{emp.full_name}</span>
                          <span className="font-mono text-[10px] text-grafana-neutral font-normal">
                            #{emp.employee_id}
                          </span>
                        </div>
                        <div className="text-[11px] text-grafana-neutral font-mono truncate">
                          {emp.email}
                        </div>
                      </div>
                    </div>
                  </DataTable.Cell>

                  {/* Role & Dept */}
                  <DataTable.Cell>
                    <div className="min-w-0">
                      <div className="font-semibold text-grafana-ink truncate text-xs">
                        {emp.role_title}
                      </div>
                      <div className="text-[11px] text-grafana-neutral truncate flex items-center gap-1 mt-0.5">
                        <Building2 className="w-3 h-3 text-grafana-neutral shrink-0" />
                        {emp.department_name}
                      </div>
                    </div>
                  </DataTable.Cell>

                  {/* Compensation */}
                  <DataTable.Cell tabularNums mono>
                    <div className="text-xs font-bold text-linear-success">
                      {emp.salary
                        ? new Intl.NumberFormat('en-IN', {
                            style: 'currency',
                            currency: 'INR',
                            maximumFractionDigits: 0,
                          }).format(emp.salary)
                        : '—'}
                    </div>
                    <div className="text-[10px] text-grafana-neutral font-mono font-normal">
                      Hired: {new Date(emp.date_hired).toLocaleDateString()}
                    </div>
                  </DataTable.Cell>

                  {/* Status & Security */}
                  <DataTable.Cell>
                    <div className="flex flex-col gap-1 items-start">
                      <span
                        className={`inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full text-[11px] font-semibold border ${
                          emp.is_active
                            ? 'bg-linear-success/10 text-linear-success border-linear-success/20'
                            : 'bg-grafana-surface text-grafana-neutral border-grafana-border'
                        }`}
                      >
                        <span
                          className={`w-1.5 h-1.5 rounded-full ${
                            emp.is_active ? 'bg-linear-success' : 'bg-grafana-neutral/50'
                          }`}
                        />
                        {emp.is_active ? 'Active' : 'Deactivated'}
                      </span>
                      <span className="text-[10px] font-mono text-grafana-neutral flex items-center gap-1">
                        <ShieldCheck className="w-3 h-3 text-linear-success" />
                        PII Encrypted
                      </span>
                    </div>
                  </DataTable.Cell>

                  {/* Row Actions */}
                  <DataTable.Cell align="right">
                    <div
                      className="flex items-center justify-end gap-1.5"
                      onClick={(e) => e.stopPropagation()}
                    >
                      <Button
                        size="icon-xs"
                        variant="ghost"
                        portalTheme="hr"
                        onClick={() => openSheet(emp, 'salary')}
                        title="Adjust Compensation"
                        aria-label={`Adjust compensation for ${emp.full_name}`}
                        className="text-linear-success hover:bg-linear-success/10 hover:border-linear-success/20"
                        leftIcon={<DollarSign className="w-3.5 h-3.5" />}
                      />
                      <Button
                        size="icon-xs"
                        variant="ghost"
                        portalTheme="hr"
                        onClick={() => openSheet(emp, 'edit')}
                        title="Edit Profile"
                        aria-label={`Edit profile for ${emp.full_name}`}
                        className="text-grafana-neutral hover:text-grafana-blue hover:bg-grafana-blue/10 hover:border-grafana-blue/20"
                        leftIcon={<Edit3 className="w-3.5 h-3.5" />}
                      />
                      <Button
                        size="icon-xs"
                        variant="secondary"
                        portalTheme="hr"
                        onClick={() => openSheet(emp, 'overview')}
                        title="Inspect Record Details"
                        aria-label={`Inspect record details for ${emp.full_name}`}
                        className="text-grafana-neutral hover:text-black"
                        leftIcon={<User className="w-3.5 h-3.5" />}
                      />
                    </div>
                  </DataTable.Cell>
                </DataTable.Row>
              );
            })
          )}
        </DataTable.Body>
      </DataTable.Root>

      {/* Pagination Footer */}
      {data && data.pages > 1 && (
        <div className="bg-white px-4 py-3 rounded-lg border border-grafana-border flex items-center justify-between shadow-2xs">
          <div className="text-xs text-grafana-neutral font-mono">
            Showing <span className="font-bold text-grafana-ink">{(page - 1) * limit + 1}</span>–
            <span className="font-bold text-grafana-ink">
              {Math.min(page * limit, data.total)}
            </span>{' '}
            of <span className="font-bold text-grafana-ink">{data.total}</span> employees
          </div>
          <div className="flex items-center gap-1.5">
            <Button
              variant="secondary"
              size="sm"
              portalTheme="hr"
              onClick={() => setPage((p) => Math.max(1, p - 1))}
              disabled={page === 1}
              leftIcon={<ChevronLeft className="h-3.5 w-3.5" />}
            >
              Prev
            </Button>
            <span className="px-2.5 py-1 text-xs font-mono text-grafana-neutral">
              Page {page} / {data.pages}
            </span>
            <Button
              variant="secondary"
              size="sm"
              portalTheme="hr"
              onClick={() => setPage((p) => Math.min(data.pages, p + 1))}
              disabled={page === data.pages}
              rightIcon={<ChevronRight className="h-3.5 w-3.5" />}
            >
              Next
            </Button>
          </div>
        </div>
      )}

      {/* Slide-Over Inspector */}
      <EmployeeSheet
        employee={selectedEmployee}
        isOpen={isSheetOpen}
        initialTab={sheetTab}
        onClose={() => setIsSheetOpen(false)}
      />
    </div>
  );
}
