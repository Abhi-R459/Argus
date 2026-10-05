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
  const [focusedRowIndex, setFocusedRowIndex] = useState<number>(-1);

  // Debounce search query
  useEffect(() => {
    const handler = setTimeout(() => {
      setDebouncedSearch(search);
      setPage(1);
    }, 350);
    return () => clearTimeout(handler);
  }, [search]);

  const limit = 12;

  // Query employees with server-side filters
  const { data, isLoading, isError, isFetching } = useQuery<PaginatedResponse>({
    queryKey: ['employees', page, debouncedSearch, selectedDept, selectedStatus],
    queryFn: () => {
      const searchParam = debouncedSearch ? `&search=${encodeURIComponent(debouncedSearch)}` : '';
      const deptParam = selectedDept !== 'all' ? `&department=${encodeURIComponent(selectedDept)}` : '';
      const statusParam = selectedStatus !== 'all' ? `&is_active=${selectedStatus === 'active'}` : '';
      return fetchWithAuth(
        `/employees?page=${page}&limit=${limit}${searchParam}${deptParam}${statusParam}`,
        {},
        getToken
      );
    },
    placeholderData: (prev) => prev,
    refetchInterval: 3000,
  });

  // Query departments for filtering
  const { data: departments = [] } = useQuery<DepartmentItem[]>({
    queryKey: ['departments'],
    queryFn: () => fetchDepartments(() => getToken()),
    staleTime: 300000,
  });

  const items = data?.items ?? [];

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
        setPage(1);
      },
    });
  }
  if (selectedDept !== 'all') {
    activeFilters.push({
      id: 'dept',
      label: 'Department',
      value: selectedDept,
      onRemove: () => {
        setSelectedDept('all');
        setPage(1);
      },
    });
  }
  if (selectedStatus !== 'all') {
    activeFilters.push({
      id: 'status',
      label: 'Status',
      value: selectedStatus === 'active' ? 'Active' : 'Deactivated',
      onRemove: () => {
        setSelectedStatus('all');
        setPage(1);
      },
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
    itemCount: items.length,
    selectedIndex: focusedRowIndex,
    onSelectIndex: (idx) => setFocusedRowIndex(idx),
    onPeek: (idx) => {
      const emp = items[idx];
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
            <Search className="w-3.5 h-3.5 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2 pointer-events-none" />
            <input
              ref={searchInputRef}
              id="hr-employee-directory-search"
              name="search"
              type="text"
              autoComplete="off"
              autoCorrect="off"
              autoCapitalize="off"
              spellCheck={false}
              data-lpignore="true"
              data-form-type="other"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search personnel directory by name or ID... (/)"
              className="w-full pl-9 pr-7 py-2 bg-white border border-slate-200 rounded-xl text-xs text-slate-900 placeholder-slate-400 focus:outline-none focus:border-slate-900 focus:ring-4 focus:ring-portal-primary/20 transition-[color,background-color,border-color,box-shadow] duration-150 ease-out shadow-2xs"
            />
            {search && (
              <button
                type="button"
                onClick={() => setSearch('')}
                aria-label="Clear search input"
                className="absolute right-2.5 top-1/2 -translate-y-1/2 text-xs text-slate-400 hover:text-slate-700 p-0.5 rounded focus-visible:outline-none"
              >
                ×
              </button>
            )}
          </div>

          {/* Department Filter */}
          <div className="relative flex items-center">
            <Building2 className="w-3.5 h-3.5 text-slate-400 absolute left-3 pointer-events-none" />
            <select
              value={selectedDept}
              onChange={(e) => {
                setSelectedDept(e.target.value);
                setPage(1);
              }}
              className="pl-9 pr-7 py-2 bg-white border border-slate-200 rounded-xl text-xs text-slate-700 focus:outline-none focus:border-slate-900 focus:ring-4 focus:ring-portal-primary/20 cursor-pointer shadow-2xs"
            >
              <option value="all">All Departments</option>
              {departments.map((dept) => (
                <option key={dept.department_id} value={dept.name}>
                  {dept.name}
                </option>
              ))}
            </select>
          </div>

          {/* Status Filter Segmented Control */}
          <div className="flex items-center rounded-xl border border-slate-200 p-0.5 bg-slate-100/70 shadow-2xs text-xs">
            <button
              type="button"
              aria-pressed={selectedStatus === 'all'}
              onClick={() => {
                setSelectedStatus('all');
                setPage(1);
              }}
              className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-[color,background-color,box-shadow] duration-150 ease-out ${
                selectedStatus === 'all'
                  ? 'bg-white text-slate-900 shadow-xs font-semibold'
                  : 'text-slate-500 hover:text-slate-900'
              }`}
            >
              All
            </button>
            <button
              type="button"
              aria-pressed={selectedStatus === 'active'}
              onClick={() => {
                setSelectedStatus('active');
                setPage(1);
              }}
              className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-[color,background-color,box-shadow] duration-150 ease-out ${
                selectedStatus === 'active'
                  ? 'bg-white text-slate-900 shadow-xs font-semibold'
                  : 'text-slate-500 hover:text-slate-900'
              }`}
            >
              Active
            </button>
            <button
              type="button"
              aria-pressed={selectedStatus === 'inactive'}
              onClick={() => {
                setSelectedStatus('inactive');
                setPage(1);
              }}
              className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-[color,background-color,box-shadow] duration-150 ease-out ${
                selectedStatus === 'inactive'
                  ? 'bg-white text-slate-900 shadow-xs font-semibold'
                  : 'text-slate-500 hover:text-slate-900'
              }`}
            >
              Deactivated
            </button>
          </div>
        </div>

        <div className="flex items-center gap-2 text-xs text-slate-400 font-mono">
          {isFetching && <span className="text-[11px] text-slate-600 font-medium">Updating…</span>}
          <span>{data?.total ?? 0} records</span>
        </div>
      </FilterBar>

      {/* Main Table Container */}
      <DataTable.Root portalTheme="hr">
        <DataTable.Header portalTheme="hr">
          <tr>
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
          </tr>
        </DataTable.Header>

        {isLoading ? (
          <SkeletonRows rowCount={8} columnCount={5} portalTheme="hr" />
        ) : (
          <DataTable.Body portalTheme="hr">
            {isError ? (
              <tr>
                <td colSpan={5} className="py-12 text-center text-xs text-rose-600 font-mono">
                  Failed to query employee directory from database engine.
                </td>
              </tr>
            ) : items.length === 0 ? (
              <tr>
                <td colSpan={5} className="py-12 text-center text-xs text-slate-500">
                  No employees found matching the specified parameters.
                </td>
              </tr>
            ) : (
              items.map((emp, idx) => {
                const isSelected = selectedEmployee?.employee_id === emp.employee_id;
                const isKeyboardFocused = focusedRowIndex === idx;

              return (
                <DataTable.Row
                  key={emp.employee_id}
                  portalTheme="hr"
                  isSelected={isSelected}
                  isFocused={isKeyboardFocused}
                  onClick={() => openSheet(emp, 'overview')}
                >
                  {/* Name & Email */}
                  <DataTable.Cell>
                    <div className="flex items-center gap-3">
                      <div className="w-8 h-8 rounded-xl bg-slate-100 border border-slate-200/80 flex items-center justify-center text-slate-700 font-semibold text-xs shrink-0 shadow-2xs">
                        {emp.full_name.charAt(0)}
                      </div>
                      <div className="min-w-0">
                        <div className="font-semibold text-slate-900 truncate flex items-center gap-1.5 text-xs">
                          <span>{emp.full_name}</span>
                          <span className="font-mono text-[10px] text-slate-400 font-normal">
                            #{emp.employee_id}
                          </span>
                        </div>
                        <div className="text-[11px] text-slate-500 font-mono truncate">
                          {emp.email}
                        </div>
                      </div>
                    </div>
                  </DataTable.Cell>

                  {/* Role & Dept */}
                  <DataTable.Cell>
                    <div className="min-w-0">
                      <div className="font-medium text-slate-900 truncate text-xs">
                        {emp.role_title}
                      </div>
                      <div className="text-[11px] text-slate-500 truncate flex items-center gap-1 mt-0.5">
                        <Building2 className="w-3 h-3 text-slate-400 shrink-0" />
                        {emp.department_name}
                      </div>
                    </div>
                  </DataTable.Cell>

                  {/* Compensation */}
                  <DataTable.Cell tabularNums mono>
                    <div className="text-xs font-semibold text-emerald-700">
                      {emp.salary
                        ? new Intl.NumberFormat('en-IN', {
                            style: 'currency',
                            currency: 'INR',
                            maximumFractionDigits: 0,
                          }).format(emp.salary)
                        : '—'}
                    </div>
                    <div className="text-[10px] text-slate-400 font-mono font-normal">
                      Hired: {new Date(emp.date_hired).toLocaleDateString()}
                    </div>
                  </DataTable.Cell>

                  {/* Status & Security */}
                  <DataTable.Cell>
                    <div className="flex flex-col gap-1 items-start">
                      <span
                        className={`inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-[11px] font-medium border ${
                          emp.is_active
                            ? 'bg-emerald-50 text-emerald-700 border-emerald-200/80'
                            : 'bg-slate-100 text-slate-500 border-slate-200'
                        }`}
                      >
                        <span
                          className={`w-1.5 h-1.5 rounded-full ${
                            emp.is_active ? 'bg-emerald-500' : 'bg-slate-400'
                          }`}
                        />
                        {emp.is_active ? 'Active' : 'Deactivated'}
                      </span>
                      <span className="text-[10px] font-mono text-slate-400 flex items-center gap-1">
                        <ShieldCheck className="w-3 h-3 text-emerald-600" />
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
                        className="text-emerald-700 hover:bg-emerald-50 hover:border-emerald-200 rounded-lg"
                        leftIcon={<DollarSign className="w-3.5 h-3.5" />}
                      />
                      <Button
                        size="icon-xs"
                        variant="ghost"
                        portalTheme="hr"
                        onClick={() => openSheet(emp, 'edit')}
                        title="Edit Profile"
                        aria-label={`Edit profile for ${emp.full_name}`}
                        className="text-slate-500 hover:text-slate-900 hover:bg-slate-100 rounded-lg"
                        leftIcon={<Edit3 className="w-3.5 h-3.5" />}
                      />
                      <Button
                        size="icon-xs"
                        variant="secondary"
                        portalTheme="hr"
                        onClick={() => openSheet(emp, 'overview')}
                        title="Inspect Record Details"
                        aria-label={`Inspect record details for ${emp.full_name}`}
                        className="text-slate-600 hover:text-slate-900 rounded-lg"
                        leftIcon={<User className="w-3.5 h-3.5" />}
                      />
                    </div>
                  </DataTable.Cell>
                </DataTable.Row>
              );
            })
          )}
        </DataTable.Body>
      )}
      </DataTable.Root>

      {/* Pagination Footer */}
      {data && data.pages > 1 && (
        <div className="bg-white px-4 py-3 rounded-xl border border-slate-200/80 flex items-center justify-between shadow-xs">
          <div className="text-xs text-slate-500 font-mono">
            Showing <span className="font-semibold text-slate-900">{(page - 1) * limit + 1}</span>–
            <span className="font-semibold text-slate-900">
              {Math.min(page * limit, data.total)}
            </span>{' '}
            of <span className="font-semibold text-slate-900">{data.total}</span> employees
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
            <span className="px-2.5 py-1 text-xs font-mono text-slate-500">
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
